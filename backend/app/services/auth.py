from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import hash_password, random_token, stable_private_id, token_hash, verify_password
from ..models import AuditLog, AuthSession, PasswordResetToken, User, UserPreference


SESSION_COOKIE = "bw_session"
CSRF_HEADER = "X-CSRF-Token"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def public_user(user: User) -> dict:
    preference = user.preference
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar": user.avatar,
        "role": user.role,
        "status": user.status,
        "ai_enabled": bool(preference and preference.ai_enabled),
        "goal": preference.goal if preference else "延续话题",
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def audit(db: Session, actor_id: str | None, action: str, target_type: str | None = None, target_id: str | None = None, metadata: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, metadata_json=metadata or {}))


def register_user(db: Session, email: str, password: str, display_name: str) -> User:
    email = normalize_email(email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    user = User(email=email, password_hash=hash_password(password), display_name=display_name.strip())
    user.preference = UserPreference(goal="延续话题", ai_enabled=False)
    db.add(user)
    db.flush()
    audit(db, user.id, "auth.register", "user", user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if not user or not verify_password(user.password_hash, password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码不正确")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号当前不可用")
    return user


def create_login_session(db: Session, user: User, request: Request, response: Response) -> str:
    raw_token = random_token()
    csrf_token = random_token(24)
    now = utcnow()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=token_hash(raw_token),
        csrf_hash=token_hash(csrf_token),
        created_at=now,
        last_seen_at=now,
        idle_expires_at=now + timedelta(days=settings.session_idle_days),
        absolute_expires_at=now + timedelta(days=settings.session_absolute_days),
        ip_hash=stable_private_id(request.client.host if request.client else "unknown", "ip"),
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(auth_session)
    user.last_login_at = now
    audit(db, user.id, "auth.login", "auth_session", auth_session.id)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_absolute_days * 86400,
        path="/",
    )
    response.set_cookie(
        "bw_csrf",
        csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_absolute_days * 86400,
        path="/",
    )
    return csrf_token


def resolve_session(db: Session, raw_token: str | None) -> tuple[User, AuthSession] | None:
    if not raw_token:
        return None
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token)))
    if not auth_session:
        return None
    now = utcnow()
    if aware(auth_session.idle_expires_at) <= now or aware(auth_session.absolute_expires_at) <= now:
        db.delete(auth_session)
        db.commit()
        return None
    user = db.get(User, auth_session.user_id)
    if not user or user.status != "active":
        db.delete(auth_session)
        db.commit()
        return None
    if (now - aware(auth_session.last_seen_at)).total_seconds() > 300:
        auth_session.last_seen_at = now
        auth_session.idle_expires_at = min(
            now + timedelta(days=settings.session_idle_days), aware(auth_session.absolute_expires_at)
        )
        db.commit()
    return user, auth_session


def revoke_session(db: Session, auth_session: AuthSession, response: Response) -> None:
    audit(db, auth_session.user_id, "auth.logout", "auth_session", auth_session.id)
    db.delete(auth_session)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("bw_csrf", path="/")


def revoke_all_sessions(db: Session, user_id: str, except_session_id: str | None = None) -> None:
    statement = delete(AuthSession).where(AuthSession.user_id == user_id)
    if except_session_id:
        statement = statement.where(AuthSession.id != except_session_id)
    db.execute(statement)


def create_password_reset(db: Session, email: str) -> tuple[User | None, str | None]:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if not user:
        return None, None
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    raw_token = random_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash(raw_token), expires_at=utcnow() + timedelta(minutes=30)))
    audit(db, user.id, "auth.password_reset_requested", "user", user.id)
    db.commit()
    return user, raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    item = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(raw_token)))
    if not item or item.used_at or aware(item.expires_at) <= utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "重置链接无效或已过期")
    user = db.get(User, item.user_id)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "重置链接无效或已过期")
    user.password_hash = hash_password(new_password)
    item.used_at = utcnow()
    revoke_all_sessions(db, user.id)
    audit(db, user.id, "auth.password_reset_completed", "user", user.id)
    db.commit()
    return user

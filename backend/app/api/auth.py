from __future__ import annotations

from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import hash_password, token_hash, verify_password
from ..db import get_db
from ..models import User, UserPreference
from ..services.auth import (
    SESSION_COOKIE,
    audit,
    authenticate,
    create_login_session,
    create_password_reset,
    public_user,
    register_user,
    reset_password,
    revoke_all_sessions,
    revoke_session,
)
from ..services.mail import send_password_reset
from .deps import AuthContext, current_context
from .schemas import ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest


router = APIRouter(prefix="/auth", tags=["账号"])
oauth = OAuth()
if settings.oidc_enabled and settings.oidc_issuer and settings.oidc_client_id:
    oauth.register(
        name="oidc",
        server_metadata_url=f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        client_kwargs={"scope": "openid email profile"},
    )


def auth_payload(user: User, csrf_token: str) -> dict:
    return {"user": public_user(user), "csrf_token": csrf_token}


@router.get("/capabilities")
def capabilities() -> dict:
    return {"password_login": True, "oidc_enabled": settings.oidc_enabled, "oidc_display_name": settings.oidc_display_name}


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user = register_user(db, str(payload.email), payload.password, payload.display_name)
    csrf_token = create_login_session(db, user, request, response)
    return auth_payload(user, csrf_token)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user = authenticate(db, str(payload.email), payload.password)
    csrf_token = create_login_session(db, user, request, response)
    return auth_payload(user, csrf_token)


@router.get("/me")
def me(context: AuthContext = Depends(current_context)) -> dict:
    return auth_payload(context.user, "")


@router.post("/logout", status_code=204)
def logout(response: Response, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    revoke_session(db, context.session, response)


@router.post("/sessions/revoke", status_code=204)
def revoke_other_sessions(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    revoke_all_sessions(db, context.user.id, context.session.id)
    audit(db, context.user.id, "auth.revoke_other_sessions", "user", context.user.id)
    db.commit()


@router.post("/change-password", status_code=204)
def change_password(payload: ChangePasswordRequest, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    if not verify_password(context.user.password_hash, payload.current_password):
        raise HTTPException(400, "当前密码不正确")
    context.user.password_hash = hash_password(payload.new_password)
    revoke_all_sessions(db, context.user.id, context.session.id)
    audit(db, context.user.id, "auth.password_changed", "user", context.user.id)
    db.commit()


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user, raw_token = create_password_reset(db, str(payload.email))
    if user and raw_token:
        try:
            send_password_reset(user.email, raw_token)
        # 找回密码接口始终返回同一结果，既不泄露账号是否存在，也不把
        # SMTP 暂时故障暴露给匿名调用者。邮件系统应通过监控单独告警。
        except Exception:
            pass
    result = {"message": "如果该邮箱已注册，重置说明将会发送。"}
    if settings.dev_show_reset_token and not settings.production and raw_token:
        result["development_reset_token"] = raw_token
    return result


@router.post("/reset-password", status_code=204)
def complete_password_reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_password(db, payload.token, payload.new_password)


@router.get("/oidc/login")
async def oidc_login(request: Request):
    if not settings.oidc_enabled or not getattr(oauth, "oidc", None):
        raise HTTPException(404, "OIDC 登录未配置")
    redirect_uri = str(request.url_for("oidc_callback"))
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@router.get("/oidc/callback", name="oidc_callback")
async def oidc_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.oidc_enabled or not getattr(oauth, "oidc", None):
        raise HTTPException(404, "OIDC 登录未配置")
    token = await oauth.oidc.authorize_access_token(request)
    info = token.get("userinfo") or await oauth.oidc.userinfo(token=token)
    subject = str(info.get("sub") or "")
    email = str(info.get("email") or "").casefold()
    if not subject or not email:
        raise HTTPException(400, "身份提供方没有返回必要的账号信息")
    user = db.scalar(select(User).where(User.oidc_subject == subject)) or db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, display_name=str(info.get("name") or email.split("@", 1)[0]), oidc_subject=subject)
        user.preference = UserPreference()
        db.add(user)
        db.flush()
    elif not user.oidc_subject:
        user.oidc_subject = subject
    if user.status != "active":
        raise HTTPException(403, "账号当前不可用")
    response = RedirectResponse(f"{settings.frontend_url}/")
    csrf_token = create_login_session(db, user, request, response)
    response.set_cookie("bw_csrf_bootstrap", csrf_token, httponly=False, secure=settings.session_cookie_secure, samesite="lax", max_age=300)
    return response

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core.security import token_hash
from ..db import get_db
from ..models import AuthSession, User
from ..services.auth import CSRF_HEADER, SESSION_COOKIE, resolve_session


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def current_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    resolved = resolve_session(db, request.cookies.get(SESSION_COOKIE))
    if not resolved:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    user, auth_session = resolved
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not hmac.compare_digest(token_hash(supplied), auth_session.csrf_hash):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "安全校验失败，请刷新页面后重试")
    return AuthContext(user=user, session=auth_session)


def current_admin(context: AuthContext = Depends(current_context)) -> AuthContext:
    if context.user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return context

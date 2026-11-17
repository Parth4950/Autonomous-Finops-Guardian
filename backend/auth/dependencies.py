from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.models.auth import User, UserSession
from backend.auth.security import token_hash
from backend.config import cors_allow_origins

SESSION_COOKIE = "finops_session"
CSRF_COOKIE = "finops_csrf"


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    origin = request.headers.get("origin", "")
    if not origin or origin not in cors_allow_origins() or not cookie or not header or cookie != header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def current_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(session_token)))
    now = datetime.now(timezone.utc)
    if row is None or row.revoked_at is not None or row.expires_at.replace(tzinfo=timezone.utc) <= now or not row.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        origin = request.headers.get("origin", "")
        if not origin or origin not in cors_allow_origins() or not csrf_cookie or not csrf_header or csrf_cookie != csrf_header or token_hash(csrf_cookie) != row.csrf_token_hash:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    return row.user

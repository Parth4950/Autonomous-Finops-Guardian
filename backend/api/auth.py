from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.dependencies import CSRF_COOKIE, SESSION_COOKIE, current_user, require_csrf
from backend.auth.security import SESSION_SECONDS, expires_at, hash_password, new_token, token_hash, verify_password
from backend.config import is_hosted_deployment
from backend.db.session import get_db
from backend.models.auth import User, UserSession, utcnow
from backend.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


def _set_cookie(response: Response, name: str, value: str, *, http_only: bool, max_age: int) -> None:
    hosted = is_hosted_deployment()
    response.set_cookie(name, value, max_age=max_age, httponly=http_only, secure=hosted, samesite="none" if hosted else "lax", path="/")


def _issue(db: Session, user: User, response: Response) -> str:
    raw_session, raw_csrf = new_token(), new_token()
    db.add(UserSession(user_id=user.id, token_hash=token_hash(raw_session), csrf_token_hash=token_hash(raw_csrf), expires_at=expires_at()))
    db.commit()
    _set_cookie(response, SESSION_COOKIE, raw_session, http_only=True, max_age=SESSION_SECONDS)
    _set_cookie(response, CSRF_COOKIE, raw_csrf, http_only=True, max_age=SESSION_SECONDS)
    return raw_csrf


def _clear_auth_cookies(response: Response) -> None:
    hosted = is_hosted_deployment()
    same_site = "none" if hosted else "lax"
    response.delete_cookie(SESSION_COOKIE, path="/", secure=hosted, httponly=True, samesite=same_site)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=hosted, httponly=True, samesite=same_site)


@router.get("/csrf")
def csrf(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    # Cross-origin browser code cannot read a cookie owned by the API origin.
    # Return only the anti-CSRF value for an in-memory request header; the
    # server still validates it against the cookie on every state-changing call.
    # After a page reload, retain a matching session-bound token; if the cookie
    # is absent or stale, rotate both the cookie and that session's stored hash.
    csrf_token = ""
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(session_token)))
        now = datetime.now(timezone.utc)
        if (
            session is not None
            and session.revoked_at is None
            and session.expires_at.replace(tzinfo=timezone.utc) > now
            and session.user.is_active
        ):
            existing_csrf = request.cookies.get(CSRF_COOKIE, "")
            if existing_csrf and hmac.compare_digest(token_hash(existing_csrf), session.csrf_token_hash):
                csrf_token = existing_csrf
            else:
                csrf_token = new_token()
                session.csrf_token_hash = token_hash(csrf_token)
                db.commit()
    if not csrf_token:
        csrf_token = new_token()
    _set_cookie(response, CSRF_COOKIE, csrf_token, http_only=True, max_age=SESSION_SECONDS)
    return {"csrf_token": csrf_token}


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    require_csrf(request)
    email, username = str(payload.email).strip().lower(), payload.username.strip().lower()
    exists = db.scalar(select(User.id).where((func.lower(User.email) == email) | (func.lower(User.username) == username)))
    if exists:
        raise HTTPException(status_code=409, detail="Email or username is already registered")
    user = User(full_name=payload.full_name.strip(), username=username, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username is already registered") from None
    db.refresh(user)
    csrf_token = _issue(db, user, response)
    return AuthResponse(user=UserResponse.model_validate(user, from_attributes=True), csrf_token=csrf_token)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    require_csrf(request)
    user = db.scalar(select(User).where(func.lower(User.email) == str(payload.email).strip().lower()))
    if user is None or not verify_password(user.password_hash, payload.password) or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    csrf_token = _issue(db, user, response)
    return AuthResponse(user=UserResponse.model_validate(user, from_attributes=True), csrf_token=csrf_token)


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db), session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> None:
    row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(session_token or ""), UserSession.user_id == user.id))
    if row:
        row.revoked_at = utcnow()
        db.commit()
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


@router.get("/profile", response_model=UserResponse, include_in_schema=False)
def profile(user: User = Depends(current_user)) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


@router.patch("/profile", response_model=UserResponse)
@router.patch("/me", response_model=UserResponse, include_in_schema=False)
def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if payload.full_name is not None:
        cleaned_name = payload.full_name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail="Full name cannot be empty")
        user.full_name = cleaned_name

    if payload.username is not None:
        cleaned_username = payload.username.strip().lower()
        conflict = db.scalar(
            select(User.id).where(func.lower(User.username) == cleaned_username, User.id != user.id)
        )
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Username is already taken")
        user.username = cleaned_username

    if payload.email is not None:
        cleaned_email = str(payload.email).strip().lower()
        conflict = db.scalar(
            select(User.id).where(func.lower(User.email) == cleaned_email, User.id != user.id)
        )
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Email is already registered")
        user.email = cleaned_email

    user.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username is already registered") from None
    db.refresh(user)
    return UserResponse.model_validate(user, from_attributes=True)


@router.post("/logout-all", status_code=204)
def logout_all(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update({UserSession.revoked_at: utcnow()})
    db.commit()
    _clear_auth_cookies(response)


@router.post("/change-password", status_code=204)
def change_password(payload: ChangePasswordRequest, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).update({UserSession.revoked_at: utcnow()})
    db.commit()
    _clear_auth_cookies(response)

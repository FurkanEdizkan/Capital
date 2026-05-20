"""Auth endpoints — login, token refresh, current user."""

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import select

from auth import ratelimit
from auth.deps import CurrentUser, SessionDep
from auth.models import User
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    username: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username),
    )


@router.post("/login", response_model=TokenPair)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> TokenPair:
    """Exchange operator credentials for an access + refresh token pair.

    Rate-limited: repeated failures lock the username out (brute-force guard).
    """
    key = form.username.lower()
    locked_for = ratelimit.is_locked(key)
    if locked_for:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts — try again in {int(locked_for) // 60 + 1} min",
        )

    user = session.exec(select(User).where(User.username == form.username)).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(form.password, user.password_hash)
    ):
        ratelimit.record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    ratelimit.reset(key)
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, session: SessionDep) -> TokenPair:
    """Issue a fresh token pair from a valid refresh token."""
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    user = session.exec(select(User).where(User.username == payload.get("sub"))).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return _tokens(user)


@router.get("/me", response_model=UserInfo)
def me(user: CurrentUser) -> UserInfo:
    """Return the currently authenticated operator."""
    return UserInfo(username=user.username, role=user.role)

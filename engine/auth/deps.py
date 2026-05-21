"""FastAPI auth dependencies — current-user resolution and role gating."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from auth.api_tokens import looks_like_api_token, verify_api_token
from auth.models import Role, User
from auth.security import decode_token
from db import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the authenticated operator from a bearer credential.

    The credential is either an interactive JWT access token or an API token
    (programmatic / agent access). An API token resolves to a synthetic,
    non-persisted principal carrying the token's role.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if looks_like_api_token(token):
        api_token = verify_api_token(session, token)
        if api_token is None:
            raise credentials_error
        return User(
            username=f"token:{api_token.name}",
            password_hash="",  # noqa: S106 — synthetic principal, no password
            role=api_token.role,
            is_active=True,
        )

    try:
        payload = decode_token(token, "access")
    except jwt.InvalidTokenError as exc:
        raise credentials_error from exc

    username = payload.get("sub")
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[[User], User]:
    """Dependency factory — gates an endpoint to the given role(s).

    The UI also hides what a role can't use, but the API enforces it here so
    the gate cannot be bypassed.
    """

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )
        return user

    return checker


# Common gate: admin-only endpoints (Settings, Users, mode switching, …).
require_admin = require_role(Role.admin.value)

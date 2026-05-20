"""Password hashing (bcrypt) and JWT access/refresh token helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from config import settings


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time check of a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def _encode(claims: dict[str, Any], ttl: timedelta, token_type: str) -> str:
    now = datetime.now(UTC)
    payload = {**claims, "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(username: str, role: str) -> str:
    return _encode(
        {"sub": username, "role": role},
        timedelta(minutes=settings.access_token_ttl_minutes),
        "access",
    )


def create_refresh_token(username: str) -> str:
    return _encode(
        {"sub": username},
        timedelta(days=settings.refresh_token_ttl_days),
        "refresh",
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises `jwt.InvalidTokenError` on failure."""
    payload: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected a {expected_type} token")
    return payload

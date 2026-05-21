"""API tokens — role-scoped, revocable credentials for programmatic access.

External agents and the MCP server authenticate with these instead of an
interactive login. A token is high-entropy, so it is stored as a plain
SHA-256 hash (bcrypt's slow KDF is unnecessary) and shown to the operator
only once, at creation.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlmodel import Session, select

from auth.models import ApiToken

#: Prefix that marks a credential as an API token (vs. a JWT).
TOKEN_PREFIX = "cap_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    """Mint a new opaque API token."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def looks_like_api_token(credential: str) -> bool:
    """Whether a bearer credential is an API token rather than a JWT."""
    return credential.startswith(TOKEN_PREFIX)


def create_api_token(
    session: Session, name: str, role: str
) -> tuple[ApiToken, str]:
    """Create a token. Returns the stored row and the plaintext (shown once)."""
    plaintext = generate_token()
    row = ApiToken(name=name, token_hash=_hash(plaintext), role=role)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, plaintext


def verify_api_token(session: Session, token: str) -> ApiToken | None:
    """Return the matching, non-revoked token, stamping `last_used_at`."""
    row = session.exec(
        select(ApiToken).where(ApiToken.token_hash == _hash(token))
    ).first()
    if row is None or row.revoked:
        return None
    row.last_used_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_api_tokens(session: Session) -> list[ApiToken]:
    """Every token, newest-first — the secret is never exposed."""
    rows = session.exec(
        select(ApiToken).order_by(ApiToken.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    return list(rows)


def revoke_api_token(session: Session, token_id: int) -> bool:
    """Revoke a token by id. Returns whether a token was found."""
    row = session.get(ApiToken, token_id)
    if row is None:
        return False
    row.revoked = True
    session.add(row)
    session.commit()
    return True

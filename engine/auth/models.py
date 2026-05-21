"""Auth database models — operators and the config audit trail."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class Role(StrEnum):
    """Operator role. `admin` has full access; `user` is restricted
    (see plan: Authentication & Roles)."""

    admin = "admin"
    user = "user"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    """An operator who can log into the engine console."""

    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=64)
    password_hash: str
    role: str = Field(default=Role.user.value, max_length=16)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ApiToken(SQLModel, table=True):
    """A revocable, role-scoped token for programmatic / agent access.

    Used instead of an interactive login by the MCP server and external
    agents. The token is shown once on creation; only its SHA-256 hash is
    stored (see auth/api_tokens.py).
    """

    __tablename__ = "api_token"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=64)
    token_hash: str = Field(unique=True, index=True)
    role: str = Field(default=Role.user.value, max_length=16)
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime | None = None


class AuditLog(SQLModel, table=True):
    """Append-only record of every config-changing action — who, when, what.

    Surfaced read-only on the History page (Phase 6). Write endpoints record
    entries here via `auth.audit.record_audit`.
    """

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    actor: str = Field(index=True, max_length=64)
    action: str = Field(max_length=64)
    target: str | None = Field(default=None, max_length=128)
    detail: str | None = None
    created_at: datetime = Field(default_factory=_utcnow, index=True)

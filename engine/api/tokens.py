"""API-token management — create, list and revoke programmatic tokens.

Admin only — a token grants API access, so issuing one is privileged. The
plaintext token is returned exactly once, on creation.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.api_tokens import create_api_token, list_api_tokens, revoke_api_token
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import ApiToken, Role, User

router = APIRouter(prefix="/api/tokens", tags=["tokens"])

AdminUser = Annotated[User, Depends(require_admin)]


class ApiTokenRead(BaseModel):
    id: int
    name: str
    role: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    role: Role = Role.user


class ApiTokenCreated(ApiTokenRead):
    token: str  # plaintext — shown exactly once


def _read(token: ApiToken) -> ApiTokenRead:
    assert token.id is not None
    return ApiTokenRead(
        id=token.id,
        name=token.name,
        role=token.role,
        revoked=token.revoked,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
    )


@router.get("", response_model=list[ApiTokenRead])
def list_tokens(_: AdminUser, session: SessionDep) -> list[ApiTokenRead]:
    """Every API token, newest-first. The secret is never returned."""
    return [_read(t) for t in list_api_tokens(session)]


@router.post("", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(
    body: ApiTokenCreate, admin: AdminUser, session: SessionDep
) -> ApiTokenCreated:
    """Create a token. The plaintext is in the response and shown only here."""
    row, plaintext = create_api_token(session, body.name, body.role.value)
    record_audit(
        session,
        actor=admin.username,
        action="token.create",
        target=body.name,
        detail={"role": body.role.value},
    )
    return ApiTokenCreated(**_read(row).model_dump(), token=plaintext)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, admin: AdminUser, session: SessionDep) -> None:
    """Revoke a token by id — it can no longer authenticate."""
    if not revoke_api_token(session, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    record_audit(
        session, actor=admin.username, action="token.revoke", target=str(token_id)
    )

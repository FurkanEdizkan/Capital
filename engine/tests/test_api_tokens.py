"""Tests for API-token generation, verification and revocation."""

from sqlmodel import Session

from auth.api_tokens import (
    create_api_token,
    generate_token,
    list_api_tokens,
    looks_like_api_token,
    revoke_api_token,
    verify_api_token,
)
from auth.models import Role


def test_generated_token_has_prefix() -> None:
    token = generate_token()
    assert token.startswith("cap_")
    assert looks_like_api_token(token)
    assert not looks_like_api_token("a.jwt.token")


def test_create_and_verify(session: Session) -> None:
    row, plaintext = create_api_token(session, "agent-1", Role.user.value)
    assert plaintext.startswith("cap_")
    verified = verify_api_token(session, plaintext)
    assert verified is not None
    assert verified.id == row.id
    assert verified.last_used_at is not None  # stamped on use


def test_unknown_token_does_not_verify(session: Session) -> None:
    assert verify_api_token(session, "cap_does-not-exist") is None


def test_revoked_token_does_not_verify(session: Session) -> None:
    row, plaintext = create_api_token(session, "agent-2", Role.admin.value)
    assert row.id is not None
    assert revoke_api_token(session, row.id) is True
    assert verify_api_token(session, plaintext) is None


def test_revoke_unknown_returns_false(session: Session) -> None:
    assert revoke_api_token(session, 9999) is False


def test_list_tokens(session: Session) -> None:
    create_api_token(session, "a", Role.user.value)
    create_api_token(session, "b", Role.admin.value)
    assert len(list_api_tokens(session)) == 2

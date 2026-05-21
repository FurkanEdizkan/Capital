"""Tests for the API-token management endpoints and token authentication."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login


@pytest.fixture
def tok_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _make_token(client: TestClient, name: str, role: str) -> str:
    resp = client.post(
        "/api/tokens", json={"name": name, "role": role}, headers=_admin(client)
    )
    assert resp.status_code == 201
    return resp.json()["token"]


def test_create_requires_auth(tok_client: TestClient) -> None:
    assert tok_client.post("/api/tokens", json={"name": "x"}).status_code == 401


def test_create_list_and_revoke(tok_client: TestClient) -> None:
    headers = _admin(tok_client)
    created = tok_client.post(
        "/api/tokens", json={"name": "agent", "role": "user"}, headers=headers
    )
    assert created.status_code == 201
    body = created.json()
    assert body["token"].startswith("cap_")

    listed = tok_client.get("/api/tokens", headers=headers).json()
    assert any(t["id"] == body["id"] for t in listed)
    assert all("token" not in t for t in listed)  # the secret is never listed

    assert tok_client.delete(
        f"/api/tokens/{body['id']}", headers=headers
    ).status_code == 204


def test_admin_token_authenticates(tok_client: TestClient) -> None:
    token = _make_token(tok_client, "admin-agent", "admin")
    # The API token works as a bearer credential on an admin endpoint.
    resp = tok_client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_user_token_is_role_scoped(tok_client: TestClient) -> None:
    token = _make_token(tok_client, "reader", "user")
    # A user-role token cannot reach an admin-only endpoint.
    resp = tok_client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_revoked_token_stops_working(tok_client: TestClient) -> None:
    headers = _admin(tok_client)
    created = tok_client.post(
        "/api/tokens", json={"name": "temp", "role": "admin"}, headers=headers
    ).json()
    token = created["token"]
    tok_client.delete(f"/api/tokens/{created['id']}", headers=headers)
    resp = tok_client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401  # revoked — no longer authenticates


def test_revoke_unknown_returns_404(tok_client: TestClient) -> None:
    assert tok_client.delete(
        "/api/tokens/9999", headers=_admin(tok_client)
    ).status_code == 404

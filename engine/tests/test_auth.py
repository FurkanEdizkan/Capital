"""Auth tests — password hashing, JWT, login flow, rate limiting, role gates."""

import jwt
import pytest
from fastapi.testclient import TestClient

from auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from config import settings
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret-password")
    assert h != "s3cret-password"
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip() -> None:
    token = create_access_token("ada", "admin")
    payload = decode_token(token, "access")
    assert payload["sub"] == "ada"
    assert payload["role"] == "admin"


def test_jwt_wrong_type_rejected() -> None:
    token = create_access_token("ada", "admin")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, "refresh")


def test_login_success(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login", data={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


def test_login_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login", data={"username": "admin", "password": "nope"}
    )
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    token = login(client, "bob", USER_PASSWORD)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "bob", "role": "user"}


def test_rate_limit_locks_out(client: TestClient) -> None:
    for _ in range(settings.login_max_attempts):
        client.post("/api/auth/login", data={"username": "admin", "password": "bad"})
    # Next attempt — even with the CORRECT password — is locked out.
    resp = client.post(
        "/api/auth/login", data={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 429


def test_users_endpoint_requires_auth(client: TestClient) -> None:
    assert client.get("/api/users").status_code == 401


def test_users_endpoint_forbidden_for_non_admin(client: TestClient) -> None:
    token = login(client, "bob", USER_PASSWORD)
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_can_list_and_create_users(client: TestClient) -> None:
    token = login(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/users", headers=headers)
    assert listed.status_code == 200
    assert {u["username"] for u in listed.json()} == {"admin", "bob"}

    created = client.post(
        "/api/users",
        headers=headers,
        json={"username": "carol", "password": "carol-pass-1", "role": "user"},
    )
    assert created.status_code == 201
    assert created.json()["username"] == "carol"

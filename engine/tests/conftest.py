"""Shared test fixtures.

Tests run against an in-memory SQLite database (the models use only portable
column types), with `get_session` overridden so nothing touches the real
Postgres. The app is NOT entered as a context manager, so the startup
lifespan (admin seeding) does not run during tests.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from auth import ratelimit
from auth.models import Role, User
from auth.security import hash_password
from db import get_session
from main import app

ADMIN_PASSWORD = "admin-pass-123"
USER_PASSWORD = "user-pass-123"


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as setup:
        setup.add(
            User(
                username="admin",
                password_hash=hash_password(ADMIN_PASSWORD),
                role=Role.admin.value,
            )
        )
        setup.add(
            User(
                username="bob",
                password_hash=hash_password(USER_PASSWORD),
                role=Role.user.value,
            )
        )
        setup.commit()
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    ratelimit._attempts.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    ratelimit._attempts.clear()


def login(client: TestClient, username: str, password: str) -> str:
    """Helper: log in and return the access token."""
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]

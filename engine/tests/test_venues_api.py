"""Tests for the venues catalogue API."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login


@pytest.fixture
def venues_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_venues_requires_auth(venues_client: TestClient) -> None:
    assert venues_client.get("/api/venues").status_code == 401


def test_lists_supported_venues(venues_client: TestClient) -> None:
    token = login(venues_client, "admin", ADMIN_PASSWORD)
    resp = venues_client.get(
        "/api/venues", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    venues = {v["name"]: v for v in resp.json()}
    assert set(venues) == {"binance", "alpaca", "polymarket"}
    # Binance is the engine's active venue; Polymarket has no sandbox.
    assert venues["binance"]["active"] is True
    assert venues["alpaca"]["active"] is False
    assert venues["polymarket"]["supports_sandbox"] is False

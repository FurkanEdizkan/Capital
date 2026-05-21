"""Tests for the venues catalogue API and the active-venue switch."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.models import Position, PositionSide


@pytest.fixture
def venues_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _open_position(session: Session) -> None:
    session.add(
        Position(
            strategy="S",
            market="spot",
            symbol="BTCUSDT",
            side=PositionSide.long.value,
            qty=Decimal("1"),
            entry_price=Decimal("100"),
            opened_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()


def test_venues_requires_auth(venues_client: TestClient) -> None:
    assert venues_client.get("/api/venues").status_code == 401


def test_lists_venues_with_binance_active_by_default(venues_client: TestClient) -> None:
    resp = venues_client.get("/api/venues", headers=_auth(venues_client))
    assert resp.status_code == 200
    venues = {v["name"]: v for v in resp.json()}
    assert set(venues) == {"binance", "alpaca", "polymarket"}
    assert venues["binance"]["active"] is True
    assert venues["alpaca"]["active"] is False
    assert venues["polymarket"]["supports_sandbox"] is False


def test_set_active_venue(venues_client: TestClient) -> None:
    resp = venues_client.put(
        "/api/venues/active", json={"venue": "alpaca"}, headers=_auth(venues_client)
    )
    assert resp.status_code == 200
    venues = {v["name"]: v["active"] for v in resp.json()}
    assert venues == {"binance": False, "alpaca": True, "polymarket": False}


def test_set_active_unknown_venue_returns_404(venues_client: TestClient) -> None:
    resp = venues_client.put(
        "/api/venues/active", json={"venue": "kraken"}, headers=_auth(venues_client)
    )
    assert resp.status_code == 404


def test_set_active_blocked_with_open_positions(
    venues_client: TestClient, session: Session
) -> None:
    _open_position(session)
    resp = venues_client.put(
        "/api/venues/active", json={"venue": "alpaca"}, headers=_auth(venues_client)
    )
    assert resp.status_code == 409


def test_set_active_requires_auth(venues_client: TestClient) -> None:
    assert (
        venues_client.put("/api/venues/active", json={"venue": "alpaca"}).status_code
        == 401
    )

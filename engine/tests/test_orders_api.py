"""Tests for the manual-order API."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api.market import get_venue_router
from auth.models import AuditLog
from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.models import Trade
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


class FakeVenue(Venue):
    """A venue that prices every symbol at a fixed value."""

    name = "binance"

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return []

    def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


@pytest.fixture
def orders_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_venue_router] = lambda: VenueRouter(
        builder=lambda *_: FakeVenue()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _order(**over: Any) -> dict[str, Any]:
    return {"symbol": "BTCUSDT", "side": "buy", "quantity": "0.5"} | over


def test_manual_order_requires_auth(orders_client: TestClient) -> None:
    assert orders_client.post("/api/orders/manual", json=_order()).status_code == 401


def test_manual_order_records_a_manual_trade(
    orders_client: TestClient, session: Session
) -> None:
    resp = orders_client.post(
        "/api/orders/manual", json=_order(), headers=_auth(orders_client)
    )
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "manual"
    trades = session.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].strategy == "manual"
    assert trades[0].mode == "sim"  # default mode


def test_manual_order_is_audited(
    orders_client: TestClient, session: Session
) -> None:
    orders_client.post(
        "/api/orders/manual", json=_order(), headers=_auth(orders_client)
    )
    entries = session.exec(
        select(AuditLog).where(AuditLog.action == "order.manual")
    ).all()
    assert len(entries) == 1


def test_manual_order_rejects_zero_quantity(orders_client: TestClient) -> None:
    resp = orders_client.post(
        "/api/orders/manual",
        json=_order(quantity="0"),
        headers=_auth(orders_client),
    )
    assert resp.status_code == 422  # quantity must be > 0

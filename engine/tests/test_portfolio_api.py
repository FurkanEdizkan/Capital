"""Tests for the portfolio API — summary, equity, positions, trades."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.market import get_stream_manager
from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.accounting import record_equity_snapshot
from trading.executors.base import Order
from trading.executors.sim import SimExecutor
from trading.models import FillSide
from trading.portfolio import set_allocation


class _FakeHub:
    def snapshot(self) -> list[object]:
        return []


class FakeStreams:
    spot = _FakeHub()
    futures = _FakeHub()


@pytest.fixture
def pf_client(session: Session) -> Iterator[TestClient]:
    # Seed a strategy with an allocation and one open position.
    set_allocation(session, "MA Cross", Decimal("10000"))
    SimExecutor(slippage_bps=Decimal("0"), fee_rate=Decimal("0")).execute(
        session,
        Order(
            strategy="MA Cross",
            market="spot",
            symbol="BTCUSDT",
            side=FillSide.buy,
            quantity=Decimal("0.1"),
        ),
        reference_price=Decimal("70000"),
    )
    record_equity_snapshot(session, {})

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_stream_manager] = lambda: FakeStreams()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_summary_requires_auth(pf_client: TestClient) -> None:
    assert pf_client.get("/api/portfolio/summary").status_code == 401


def test_summary(pf_client: TestClient) -> None:
    token = login(pf_client, "admin", ADMIN_PASSWORD)
    resp = pf_client.get(
        "/api/portfolio/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_allocated"]) == Decimal("10000")
    assert body["open_positions"] == 1


def test_positions(pf_client: TestClient) -> None:
    token = login(pf_client, "admin", ADMIN_PASSWORD)
    resp = pf_client.get(
        "/api/portfolio/positions", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"


def test_trades(pf_client: TestClient) -> None:
    token = login(pf_client, "admin", ADMIN_PASSWORD)
    resp = pf_client.get(
        "/api/portfolio/trades", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_equity_history(pf_client: TestClient) -> None:
    token = login(pf_client, "admin", ADMIN_PASSWORD)
    resp = pf_client.get(
        "/api/portfolio/equity", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_costs(pf_client: TestClient) -> None:
    token = login(pf_client, "admin", ADMIN_PASSWORD)
    resp = pf_client.get(
        "/api/portfolio/costs", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # The seeded fill is a 0.1 BTC spot buy at 70000.
    assert "spot" in body["fees_by_market"]
    assert Decimal(body["traded_volume"]) == Decimal("7000")
    assert set(body["venue_fee_rates"]) == {
        "binance",
        "alpaca",
        "polymarket",
        "binance-alpha",
    }
    assert Decimal(body["venue_fee_rates"]["alpaca"]) == Decimal("0")

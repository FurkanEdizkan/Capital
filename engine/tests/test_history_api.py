"""Tests for the history API — transaction log, audit log, CSV export."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from auth.audit import record_audit
from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.models import FillSide, Trade

_BASE = datetime(2026, 5, 1)


@pytest.fixture
def hist_client(session: Session) -> Iterator[TestClient]:
    for i in range(3):
        session.add(
            Trade(
                strategy="MA Cross BTC",
                market="spot",
                symbol="BTCUSDT",
                side=FillSide.buy.value,
                quantity=Decimal("1"),
                price=Decimal("100"),
                fee=Decimal("0.1"),
                realized_pnl=Decimal("0"),
                mode="sim",
                executed_at=_BASE + timedelta(days=i),
            )
        )
    session.commit()
    record_audit(session, actor="admin", action="settings.mode", detail={"to": "testnet"})
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_trades_requires_auth(hist_client: TestClient) -> None:
    assert hist_client.get("/api/history/trades").status_code == 401


def test_trades_returns_the_log(hist_client: TestClient) -> None:
    resp = hist_client.get("/api/history/trades", headers=_auth(hist_client))
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_trades_date_filter(hist_client: TestClient) -> None:
    # Only the day-1 and day-2 trades fall on/after this start.
    resp = hist_client.get(
        "/api/history/trades",
        params={"start": (_BASE + timedelta(days=1)).isoformat()},
        headers=_auth(hist_client),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_audit_log(hist_client: TestClient) -> None:
    resp = hist_client.get("/api/history/audit", headers=_auth(hist_client))
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "settings.mode" in actions


def test_csv_export(hist_client: TestClient) -> None:
    resp = hist_client.get("/api/history/trades.csv", headers=_auth(hist_client))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("executed_at,strategy,market,symbol")
    assert len(lines) == 1 + 3  # header + three trades

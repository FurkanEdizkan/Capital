"""Tests for the engine watchdog — heartbeat and staleness detection."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from db import get_session
from main import app
from ops.watchdog import record_heartbeat, watchdog_status
from tests.conftest import ADMIN_PASSWORD, login
from trading.models import Position, PositionSide


def _open_position(session: Session) -> None:
    session.add(
        Position(
            strategy="S",
            market="spot",
            symbol="BTCUSDT",
            side=PositionSide.long.value,
            qty=Decimal("1"),
            entry_price=Decimal("100"),
        )
    )
    session.commit()


def test_no_heartbeat_is_not_alive(session: Session) -> None:
    status = watchdog_status(session)
    assert status.alive is False
    assert status.stale is True
    assert status.alert is False  # never ran — not an alert, just absent
    assert status.last_beat is None


def test_fresh_heartbeat_is_alive(session: Session) -> None:
    record_heartbeat(session)
    status = watchdog_status(session)
    assert status.alive is True
    assert status.stale is False
    assert status.last_beat is not None


def test_stale_heartbeat_without_positions_is_not_an_alert(session: Session) -> None:
    record_heartbeat(session)
    status = watchdog_status(session, max_age_seconds=-1.0)  # force stale
    assert status.stale is True
    assert status.alive is False
    assert status.alert is False  # stale but flat — nothing at risk


def test_stale_heartbeat_with_open_position_is_an_alert(session: Session) -> None:
    record_heartbeat(session)
    _open_position(session)
    status = watchdog_status(session, max_age_seconds=-1.0)
    assert status.alert is True
    assert status.open_positions == 1


@pytest.fixture
def wd_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_watchdog_endpoint(wd_client: TestClient) -> None:
    assert wd_client.get("/api/system/watchdog").status_code == 401
    token = login(wd_client, "admin", ADMIN_PASSWORD)
    resp = wd_client.get(
        "/api/system/watchdog", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert "alive" in resp.json()

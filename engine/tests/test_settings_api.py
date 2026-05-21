"""Tests for the settings API — trading mode and Binance credentials."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from auth.models import AuditLog
from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.models import Position, PositionSide


@pytest.fixture
def settings_client(session: Session) -> Iterator[TestClient]:
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


def test_read_requires_auth(settings_client: TestClient) -> None:
    assert settings_client.get("/api/settings").status_code == 401


def test_read_defaults(settings_client: TestClient) -> None:
    resp = settings_client.get("/api/settings", headers=_auth(settings_client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "sim"
    assert body["binance_keys_configured"] is False


def test_switch_to_testnet(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/mode", json={"mode": "testnet"}, headers=_auth(settings_client)
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "testnet"


def test_live_requires_confirmation(settings_client: TestClient) -> None:
    headers = _auth(settings_client)
    assert (
        settings_client.put(
            "/api/settings/mode", json={"mode": "live"}, headers=headers
        ).status_code
        == 400
    )
    ok = settings_client.put(
        "/api/settings/mode", json={"mode": "live", "confirm": True}, headers=headers
    )
    assert ok.status_code == 200
    assert ok.json()["mode"] == "live"


def test_mode_switch_blocked_with_open_positions(
    settings_client: TestClient, session: Session
) -> None:
    _open_position(session)
    resp = settings_client.put(
        "/api/settings/mode", json={"mode": "testnet"}, headers=_auth(settings_client)
    )
    assert resp.status_code == 409


def test_store_binance_keys(settings_client: TestClient) -> None:
    headers = _auth(settings_client)
    resp = settings_client.put(
        "/api/settings/binance-keys",
        json={"api_key": "k-123", "api_secret": "s-456"},
        headers=headers,
    )
    assert resp.status_code == 204
    read = settings_client.get("/api/settings", headers=headers)
    assert read.json()["binance_keys_configured"] is True


def test_mode_change_is_audited(settings_client: TestClient, session: Session) -> None:
    settings_client.put(
        "/api/settings/mode", json={"mode": "testnet"}, headers=_auth(settings_client)
    )
    entries = session.exec(
        select(AuditLog).where(AuditLog.action == "settings.mode")
    ).all()
    assert len(entries) == 1

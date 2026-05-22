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


def test_update_ai_settings(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/ai",
        json={"provider": "openai", "model": "gpt-4o", "base_url": "", "api_key": "sk-x"},
        headers=_auth(settings_client),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_provider"] == "openai"
    assert body["ai_model"] == "gpt-4o"
    assert body["ai_key_configured"] is True


def test_mode_change_is_audited(settings_client: TestClient, session: Session) -> None:
    settings_client.put(
        "/api/settings/mode", json={"mode": "testnet"}, headers=_auth(settings_client)
    )
    entries = session.exec(
        select(AuditLog).where(AuditLog.action == "settings.mode")
    ).all()
    assert len(entries) == 1


def test_store_venue_credentials(settings_client: TestClient) -> None:
    headers = _auth(settings_client)
    resp = settings_client.put(
        "/api/settings/venue-credentials/alpaca",
        json={"fields": {"api_key": "ak-1", "api_secret": "as-2"}},
        headers=headers,
    )
    assert resp.status_code == 204
    read = settings_client.get("/api/settings", headers=headers)
    assert read.json()["venue_credentials_configured"]["alpaca"] is True
    assert read.json()["venue_credentials_configured"]["polymarket"] is False


def test_venue_credentials_reject_unknown_venue(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/venue-credentials/nasdaq",
        json={"fields": {"api_key": "x"}},
        headers=_auth(settings_client),
    )
    assert resp.status_code == 404


def test_venue_credentials_reject_wrong_fields(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/venue-credentials/alpaca",
        json={"fields": {"api_key": "x"}},  # missing api_secret
        headers=_auth(settings_client),
    )
    assert resp.status_code == 400


def test_set_llm_credentials(settings_client: TestClient) -> None:
    headers = _auth(settings_client)
    resp = settings_client.put(
        "/api/settings/llm-credentials/openai",
        json={"api_key": "sk-x", "base_url": ""},
        headers=headers,
    )
    assert resp.status_code == 200
    configured = resp.json()["llm_providers_configured"]
    assert configured["openai"] is True
    assert configured["ollama"] is True  # local — always usable
    assert configured["gemini"] is False


def test_llm_credentials_reject_unknown_provider(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/llm-credentials/skynet",
        json={"api_key": "x"},
        headers=_auth(settings_client),
    )
    assert resp.status_code == 404


def test_set_ai_spend_cap(settings_client: TestClient) -> None:
    headers = _auth(settings_client)
    resp = settings_client.put(
        "/api/settings/ai-spend-cap", json={"cap": "5.50"}, headers=headers
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["ai_spend_cap"]) == Decimal("5.50")
    assert Decimal(resp.json()["ai_spend_today"]) == Decimal("0")


def test_ai_spend_cap_rejects_negative(settings_client: TestClient) -> None:
    resp = settings_client.put(
        "/api/settings/ai-spend-cap",
        json={"cap": "-1"},
        headers=_auth(settings_client),
    )
    assert resp.status_code == 422


def test_testnet_blocked_when_active_venue_has_no_sandbox(
    settings_client: TestClient,
) -> None:
    headers = _auth(settings_client)
    settings_client.put(
        "/api/venues/active", json={"venue": "polymarket"}, headers=headers
    )
    # Polymarket has no sandbox — switching to Testnet is rejected.
    resp = settings_client.put(
        "/api/settings/mode", json={"mode": "testnet"}, headers=headers
    )
    assert resp.status_code == 409


def test_venue_credentials_audited_without_values(
    settings_client: TestClient, session: Session
) -> None:
    settings_client.put(
        "/api/settings/venue-credentials/alpaca",
        json={"fields": {"api_key": "secret-ak", "api_secret": "secret-as"}},
        headers=_auth(settings_client),
    )
    entries = session.exec(
        select(AuditLog).where(AuditLog.action == "settings.venue_credentials")
    ).all()
    assert len(entries) == 1
    assert "secret-ak" not in (entries[0].detail or "")
    assert "secret-as" not in (entries[0].detail or "")

"""Tests for the strategy management API — list, allocate, enable, close."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api.market import get_stream_manager
from api.strategies import get_trading_engine
from auth.models import AuditLog
from db import get_session
from exchange.client import Market
from main import app
from strategies.ai_strategy import AIStrategy
from strategies.base import BaseStrategy
from strategies.ma_cross import MACrossStrategy
from tests.conftest import ADMIN_PASSWORD, login
from trading.lifecycle import is_enabled
from trading.portfolio import get_allocation, set_allocation

STRAT = "MA Cross BTC"


class _FakeHub:
    def snapshot(self) -> list[object]:
        return []


class FakeStreams:
    spot = _FakeHub()
    futures = _FakeHub()


AI_STRAT = "AI Trader BTC"


class FakeEngine:
    """Minimal TradingEngine stand-in — exposes strategies and flatten()."""

    def __init__(self, strategies: list[BaseStrategy]) -> None:
        self._strategies = strategies
        self.flatten_calls: list[str] = []

    @property
    def strategies(self) -> list[BaseStrategy]:
        return self._strategies

    def flatten(self, name: str) -> int:
        self.flatten_calls.append(name)
        return 0


@pytest.fixture
def strat_client(session: Session) -> Iterator[TestClient]:
    set_allocation(session, STRAT, Decimal("5000"))
    engine = FakeEngine(
        [
            MACrossStrategy(STRAT, "BTCUSDT", market=Market.spot, timeframe="1h"),
            AIStrategy(AI_STRAT, "ETHUSDT", market=Market.spot, timeframe="1h"),
        ]
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_stream_manager] = lambda: FakeStreams()
    app.dependency_overrides[get_trading_engine] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    token = login(client, "admin", ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_list_requires_auth(strat_client: TestClient) -> None:
    assert strat_client.get("/api/strategies").status_code == 401


def test_list_strategies(strat_client: TestClient) -> None:
    resp = strat_client.get("/api/strategies", headers=_auth(strat_client))
    assert resp.status_code == 200
    rows = {r["name"]: r for r in resp.json()}
    assert rows[STRAT]["kind"] == "MA Cross"
    assert Decimal(rows[STRAT]["allocated"]) == Decimal("5000")
    # The AI strategy exposes its configured provider; others do not.
    assert rows[AI_STRAT]["ai_provider"] == "claude"
    assert rows[STRAT]["ai_provider"] is None
    assert rows[STRAT]["enabled"] is True


def test_update_allocation(strat_client: TestClient, session: Session) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{STRAT}/allocation",
        json={"allocated": "8000"},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["allocated"]) == Decimal("8000")
    assert get_allocation(session, STRAT) == Decimal("8000")


def test_update_allocation_rejects_negative(strat_client: TestClient) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{STRAT}/allocation",
        json={"allocated": "-1"},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 422


def test_enable_disable(strat_client: TestClient, session: Session) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{STRAT}/enabled",
        json={"enabled": False},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert is_enabled(session, STRAT) is False


def test_unknown_strategy_returns_404(strat_client: TestClient) -> None:
    resp = strat_client.patch(
        "/api/strategies/Nonexistent/enabled",
        json={"enabled": False},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 404


def test_close_strategy(strat_client: TestClient) -> None:
    resp = strat_client.post(
        f"/api/strategies/{STRAT}/close", headers=_auth(strat_client)
    )
    assert resp.status_code == 200
    assert resp.json() == {"closed": 0}


def test_allocation_change_is_audited(strat_client: TestClient, session: Session) -> None:
    strat_client.patch(
        f"/api/strategies/{STRAT}/allocation",
        json={"allocated": "9000"},
        headers=_auth(strat_client),
    )
    entries = session.exec(
        select(AuditLog).where(AuditLog.action == "strategy.allocation")
    ).all()
    assert len(entries) == 1
    assert entries[0].target == STRAT


def test_set_ai_model(strat_client: TestClient) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{AI_STRAT}/ai-model",
        json={"provider": "ollama", "model": "qwen2.5"},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_provider"] == "ollama"
    assert body["ai_model"] == "qwen2.5"


def test_ai_model_rejected_for_non_ai_strategy(strat_client: TestClient) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{STRAT}/ai-model",
        json={"provider": "ollama", "model": "x"},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 400


def test_ai_model_rejects_unknown_provider(strat_client: TestClient) -> None:
    resp = strat_client.patch(
        f"/api/strategies/{AI_STRAT}/ai-model",
        json={"provider": "skynet", "model": "x"},
        headers=_auth(strat_client),
    )
    assert resp.status_code == 400

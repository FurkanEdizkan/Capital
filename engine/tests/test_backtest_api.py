"""Tests for the backtest API — run a strategy over historical data."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.market import get_binance_client
from api.strategies import get_trading_engine
from db import get_session
from exchange.client import Kline, Market
from main import app
from strategies.ma_cross import MACrossStrategy
from tests.conftest import ADMIN_PASSWORD, login

STRAT = "MA Cross BTC"


def _klines(n: int) -> list[Kline]:
    """A rise-then-fall series so MA crossover enters and exits."""
    base = datetime(2024, 5, 20, tzinfo=UTC)
    out = []
    for i in range(n):
        t = base + timedelta(hours=i)
        close = 100 + (i if i < n // 2 else n - i)
        out.append(
            Kline(
                open_time=t,
                open=Decimal("100"),
                high=Decimal("200"),
                low=Decimal("50"),
                close=Decimal(close),
                volume=Decimal("1"),
                close_time=t + timedelta(minutes=59),
            )
        )
    return out


class FakeClient:
    def get_historical_klines(self, *_: Any, **__: Any) -> list[Kline]:
        return _klines(40)


class FakeEngine:
    def __init__(self, strategies: list[MACrossStrategy]) -> None:
        self._strategies = strategies

    @property
    def strategies(self) -> list[MACrossStrategy]:
        return self._strategies


@pytest.fixture
def bt_client(session: Session) -> Iterator[TestClient]:
    engine = FakeEngine(
        [MACrossStrategy(STRAT, "BTCUSDT", market=Market.spot, timeframe="1h")]
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_trading_engine] = lambda: engine
    app.dependency_overrides[get_binance_client] = lambda: FakeClient()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _run(client: TestClient, **overrides: object) -> Any:
    body = {"strategy": STRAT, "start": "2024-05-19T00:00:00", **overrides}
    return client.post("/api/backtest/run", json=body, headers=_auth(client))


def test_run_requires_auth(bt_client: TestClient) -> None:
    body = {"strategy": STRAT, "start": "2024-05-19T00:00:00"}
    assert bt_client.post("/api/backtest/run", json=body).status_code == 401


def test_run_backtest(bt_client: TestClient) -> None:
    resp = _run(bt_client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] == STRAT
    assert body["candles"] == 40
    assert len(body["equity_curve"]) == 40
    assert "metrics" in body
    assert Decimal(body["initial_capital"]) == Decimal("10000")


def test_unknown_strategy_returns_404(bt_client: TestClient) -> None:
    assert _run(bt_client, strategy="Nonexistent").status_code == 404


def test_empty_range_returns_422(bt_client: TestClient) -> None:
    # A start date after every available candle yields no data.
    assert _run(bt_client, start="2030-01-01T00:00:00").status_code == 422


def test_rejects_non_positive_capital(bt_client: TestClient) -> None:
    assert _run(bt_client, initial_capital="0").status_code == 422

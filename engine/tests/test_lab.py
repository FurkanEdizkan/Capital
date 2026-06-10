"""Tests for the Strategy Lab — comparison grids and the AI recommendation."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.providers.base import Completion, LLMError, LLMProvider
from api.ai import get_llm_provider
from api.market import get_binance_client
from db import get_session
from main import app
from marketdata.models import Candle
from strategies.registry import STRATEGY_TYPES
from tests.conftest import ADMIN_PASSWORD, login


class FakeClient:
    """BinanceClient stand-in — counts download calls, returns nothing new."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_historical_klines(self, symbol: str, interval: str = "1h", **_kw) -> list:
        self.calls.append(symbol)
        return []


class RecommendProvider(LLMProvider):
    name = "fake"

    def __init__(self, text: str, *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        if self._raises:
            raise LLMError("provider down")
        return Completion(
            text=self._text, provider=self.name, model=model or "m",
            input_tokens=10, output_tokens=5,
        )


def _seed_candles(session: Session, symbol: str, n: int = 200) -> None:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    start = base - timedelta(hours=n)
    for i in range(n):
        # A gentle rise then fall, so crossover strategies actually trade.
        drift = i if i < n // 2 else n - i
        price = Decimal(100) + Decimal(drift)
        session.add(
            Candle(
                market="spot",
                symbol=symbol,
                interval="1h",
                open_time=start + timedelta(hours=i),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=Decimal(5),
                close_time=start + timedelta(hours=i + 1),
            )
        )
    session.commit()


@pytest.fixture
def lab_client(session: Session) -> Iterator[tuple[TestClient, FakeClient]]:
    fake = FakeClient()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_binance_client] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_compare_grid_shape_and_metrics(
    lab_client: tuple[TestClient, FakeClient], session: Session
) -> None:
    client, fake = lab_client
    _seed_candles(session, "BTCUSDT")
    _seed_candles(session, "ETHUSDT")
    resp = client.post(
        "/api/lab/compare",
        json={"symbols": ["btcusdt", "ETHUSDT"], "days": 30},
        headers=_auth(client),
    )
    assert resp.status_code == 200, resp.text
    cells = resp.json()
    # All types × both symbols, candles fetched once per symbol.
    assert len(cells) == len(STRATEGY_TYPES) * 2
    assert fake.calls == ["BTCUSDT", "ETHUSDT"]
    ma = next(c for c in cells if c["type"] == "ma_cross" and c["symbol"] == "BTCUSDT")
    assert ma["error"] == ""
    assert ma["trades"] > 0
    assert len(ma["equity_sparkline"]) > 0
    assert Decimal(str(ma["final_equity"])) != Decimal(0)


def test_compare_handles_missing_data_per_cell(
    lab_client: tuple[TestClient, FakeClient], session: Session
) -> None:
    client, _ = lab_client
    _seed_candles(session, "BTCUSDT")
    resp = client.post(
        "/api/lab/compare",
        json={"symbols": ["BTCUSDT", "NODATAUSDT"], "types": ["rsi"]},
        headers=_auth(client),
    )
    cells = {c["symbol"]: c for c in resp.json()}
    assert cells["BTCUSDT"]["error"] == ""
    assert "no candle data" in cells["NODATAUSDT"]["error"]


def test_compare_bounds_are_enforced(
    lab_client: tuple[TestClient, FakeClient],
) -> None:
    client, _ = lab_client
    too_many = [f"S{i}USDT" for i in range(9)]
    resp = client.post(
        "/api/lab/compare", json={"symbols": too_many}, headers=_auth(client)
    )
    assert resp.status_code == 422
    resp = client.post(
        "/api/lab/compare",
        json={"symbols": ["BTCUSDT"], "types": ["bogus"]},
        headers=_auth(client),
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/lab/compare",
        json={"symbols": ["BTCUSDT"], "timeframe": "13m"},
        headers=_auth(client),
    )
    assert resp.status_code == 400


def _with_provider(provider: LLMProvider) -> None:
    app.dependency_overrides[get_llm_provider] = lambda: provider


def test_recommend_backtests_the_ai_pick(
    lab_client: tuple[TestClient, FakeClient], session: Session
) -> None:
    client, _ = lab_client
    _seed_candles(session, "SOLUSDT")
    _with_provider(
        RecommendProvider(
            json.dumps(
                {
                    "strategy_type": "rsi",
                    "params": {"period": 7},
                    "reasoning": "mean-reverting regime",
                }
            )
        )
    )
    resp = client.post(
        "/api/lab/recommend", json={"symbol": "solusdt"}, headers=_auth(client)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["strategy_type"] == "rsi"
    assert body["params"]["period"] == "7"  # params echo as strings
    assert body["reasoning"] == "mean-reverting regime"
    assert body["cell"]["symbol"] == "SOLUSDT"
    assert body["cell"]["error"] == ""


def test_recommend_rejects_garbage_responses(
    lab_client: tuple[TestClient, FakeClient], session: Session
) -> None:
    client, _ = lab_client
    _with_provider(RecommendProvider("no json here"))
    resp = client.post(
        "/api/lab/recommend", json={"symbol": "BTCUSDT"}, headers=_auth(client)
    )
    assert resp.status_code == 502
    _with_provider(
        RecommendProvider(json.dumps({"strategy_type": "bogus", "params": {}}))
    )
    resp = client.post(
        "/api/lab/recommend", json={"symbol": "BTCUSDT"}, headers=_auth(client)
    )
    assert resp.status_code == 502
    _with_provider(RecommendProvider("", raises=True))
    resp = client.post(
        "/api/lab/recommend", json={"symbol": "BTCUSDT"}, headers=_auth(client)
    )
    assert resp.status_code == 502

"""Tests for pickable strategy instances — registry, persistence, API."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api.market import get_stream_manager
from api.strategies import get_trading_engine
from db import get_session
from main import app
from strategies.builtin import all_strategies_with_instances
from strategies.models import StrategyInstance
from strategies.registry import STRATEGY_TYPES, build_strategy, coerce_params
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_strategies_api import FakeEngine, FakeStreams
from trading.models import Position, PositionSide
from trading.portfolio import get_allocation, get_max_loss


def test_every_type_builds_from_its_defaults() -> None:
    for key in STRATEGY_TYPES:
        strat = build_strategy(key, name=f"t-{key}", symbol="solusdt")
        assert strat.symbol == "SOLUSDT"
        assert strat.timeframe == "1h"


def test_coerce_params_validates_range_and_keys() -> None:
    assert coerce_params("ma_cross", {"fast": "5", "slow": "30"}) == {
        "fast": 5,
        "slow": 30,
    }
    with pytest.raises(ValueError, match="between"):
        coerce_params("ma_cross", {"fast": "0"})
    with pytest.raises(ValueError, match="unknown params"):
        coerce_params("ma_cross", {"nope": "1"})
    with pytest.raises(ValueError, match="must be a int"):
        coerce_params("ma_cross", {"fast": "abc"})
    with pytest.raises(ValueError, match="unknown strategy type"):
        coerce_params("nope", {})


def test_constructor_invariants_surface_as_value_error() -> None:
    with pytest.raises(ValueError):
        build_strategy("ma_cross", name="x", symbol="BTCUSDT", params={"fast": "30", "slow": "10"})
    with pytest.raises(ValueError):
        build_strategy("ma_cross", name="x", symbol="BTCUSDT", timeframe="bogus")


def test_build_strategy_assigns_and_validates_the_venue() -> None:
    strat = build_strategy("ma_cross", name="x", symbol="BTCUSDT", venue="binance")
    assert strat.venue == "binance"
    # Polymarket symbols are case-sensitive token ids — never uppercased.
    poly = build_strategy("dca", name="y", symbol="123abc", venue="polymarket")
    assert poly.venue == "polymarket"
    assert poly.symbol == "123abc"
    with pytest.raises(ValueError, match="unknown venue"):
        build_strategy("ma_cross", name="z", symbol="BTCUSDT", venue="kraken")


def test_instance_rows_become_strategies(session: Session) -> None:
    session.add(
        StrategyInstance(
            name="RSI SOL",
            type="rsi",
            symbol="SOLUSDT",
            params='{"period": 7}',
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    # A broken row is skipped, not fatal.
    session.add(
        StrategyInstance(
            name="Broken",
            type="gone_type",
            symbol="SOLUSDT",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()
    names = {s.name for s in all_strategies_with_instances(session)}
    assert "RSI SOL" in names
    assert "Broken" not in names


@pytest.fixture
def inst_client(session: Session) -> Iterator[tuple[TestClient, FakeEngine]]:
    engine = FakeEngine(all_strategies_with_instances(session))
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_stream_manager] = lambda: FakeStreams()
    app.dependency_overrides[get_trading_engine] = lambda: engine
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_types_endpoint_exposes_param_schemas(
    inst_client: tuple[TestClient, FakeEngine],
) -> None:
    client, _ = inst_client
    resp = client.get("/api/strategies/types", headers=_auth(client))
    assert resp.status_code == 200
    types = {t["key"]: t for t in resp.json()}
    assert set(types) == set(STRATEGY_TYPES)
    fast = next(p for p in types["ma_cross"]["params"] if p["name"] == "fast")
    assert fast == {
        "name": "fast",
        "type": "int",
        "default": "9",
        "min": "2",
        "max": "200",
        "label": "Fast SMA period",
    }
    assert "1h" in types["rsi"]["timeframes"]


def test_create_and_delete_instance_round_trip(
    inst_client: tuple[TestClient, FakeEngine], session: Session
) -> None:
    client, engine = inst_client
    headers = _auth(client)
    resp = client.post(
        "/api/strategies",
        json={
            "name": "RSI SOL 15m",
            "type": "rsi",
            "symbol": "solusdt",
            "timeframe": "15m",
            "params": {"period": "7"},
            "allocated": "2500",
            "max_loss": "100",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["symbol"] == "SOLUSDT"
    assert Decimal(body["allocated"]) == Decimal("2500")
    assert Decimal(body["max_loss"]) == Decimal("100")
    # The engine picked the new instance up immediately.
    assert any(s.name == "RSI SOL 15m" for s in engine.strategies)
    assert get_allocation(session, "RSI SOL 15m") == Decimal("2500")
    assert get_max_loss(session, "RSI SOL 15m") == Decimal("100")

    # Duplicate names are rejected.
    dup = client.post(
        "/api/strategies",
        json={"name": "RSI SOL 15m", "type": "rsi", "symbol": "SOLUSDT"},
        headers=headers,
    )
    assert dup.status_code == 409

    resp = client.delete("/api/strategies/RSI SOL 15m", headers=headers)
    assert resp.status_code == 204
    assert not any(s.name == "RSI SOL 15m" for s in engine.strategies)
    assert session.exec(select(StrategyInstance)).all() == []


def test_create_rejects_bad_params(
    inst_client: tuple[TestClient, FakeEngine],
) -> None:
    client, _ = inst_client
    resp = client.post(
        "/api/strategies",
        json={
            "name": "Bad MA",
            "type": "ma_cross",
            "symbol": "BTCUSDT",
            "params": {"fast": "50", "slow": "10"},
        },
        headers=_auth(client),
    )
    assert resp.status_code == 400


def test_delete_refuses_builtins_and_open_positions(
    inst_client: tuple[TestClient, FakeEngine], session: Session
) -> None:
    client, _ = inst_client
    headers = _auth(client)
    # Built-in (no instance row) → 404.
    assert (
        client.delete("/api/strategies/MA Cross BTC", headers=headers).status_code
        == 404
    )
    client.post(
        "/api/strategies",
        json={"name": "DCA DOGE", "type": "dca", "symbol": "DOGEUSDT"},
        headers=headers,
    )
    session.add(
        Position(
            strategy="DCA DOGE",
            market="spot",
            symbol="DOGEUSDT",
            side=PositionSide.long.value,
            qty=Decimal(1),
            entry_price=Decimal(1),
        )
    )
    session.commit()
    assert (
        client.delete("/api/strategies/DCA DOGE", headers=headers).status_code == 409
    )

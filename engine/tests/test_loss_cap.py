"""Tests for the per-strategy loss cap — breach closes and disables."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from exchange.client import Market
from tests.test_trading_engine import BuyWhenFlat, _engine
from trading.lifecycle import is_enabled
from trading.models import PositionSide, Trade
from trading.portfolio import get_max_loss, list_positions, set_max_loss


@pytest.fixture
def db_engine() -> Any:
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def factory(db_engine: Any) -> Iterator[Any]:
    yield lambda: Session(db_engine)


def test_loss_cap_breach_closes_and_disables(db_engine: Any, factory: Any) -> None:
    strat = BuyWhenFlat("MA Cross", "BTCUSDT", market=Market.spot)
    eng = _engine(factory, [strat])
    eng.tick()  # buys 1 @ 100 (plus fee — strategy is already slightly down)
    with factory() as session:
        positions = list_positions(session, strategy="MA Cross", open_only=True)
        assert len(positions) == 1
        # A cap below the fees already paid breaches on the next tick.
        set_max_loss(session, "MA Cross", Decimal("0.001"))
    eng.tick()
    with factory() as session:
        assert list_positions(session, strategy="MA Cross", open_only=True) == []
        assert not is_enabled(session, "MA Cross")
        trades = session.exec(select(Trade)).all()
        # The closing fill was recorded (entry + forced close).
        assert len(trades) == 2
        assert {t.side for t in trades} == {"buy", "sell"}


def test_loss_cap_zero_never_triggers(db_engine: Any, factory: Any) -> None:
    strat = BuyWhenFlat("MA Cross", "BTCUSDT", market=Market.spot)
    eng = _engine(factory, [strat])
    eng.tick()
    eng.tick()  # fees were paid, but the default cap (0) is disabled
    with factory() as session:
        assert get_max_loss(session, "MA Cross") == Decimal(0)
        assert is_enabled(session, "MA Cross")
        positions = list_positions(session, strategy="MA Cross", open_only=True)
        assert len(positions) == 1
        assert positions[0].side == PositionSide.long.value


def test_breached_strategy_stays_disabled_and_flat(
    db_engine: Any, factory: Any
) -> None:
    strat = BuyWhenFlat("MA Cross", "BTCUSDT", market=Market.spot)
    eng = _engine(factory, [strat])
    eng.tick()
    with factory() as session:
        set_max_loss(session, "MA Cross", Decimal("0.001"))
    eng.tick()  # breach: close + disable
    eng.tick()  # disabled — must not re-enter
    with factory() as session:
        assert list_positions(session, strategy="MA Cross", open_only=True) == []
        assert len(session.exec(select(Trade)).all()) == 2

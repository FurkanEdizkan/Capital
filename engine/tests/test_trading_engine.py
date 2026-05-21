"""Tests for the TradingEngine tick loop and the strategy framework."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from exchange.client import Kline, Market
from strategies.base import BaseStrategy, StrategyContext
from trading.engine import TradingEngine
from trading.executors.base import Order
from trading.models import FillSide, PositionSide, Trade
from trading.portfolio import list_positions, set_allocation


def _klines(n: int) -> list[Kline]:
    # End at the current hour so the newest candle passes the staleness check.
    base = datetime.now(UTC).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=n - 1)
    return [
        Kline(
            open_time=base + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=Decimal("10"),
            close_time=base + timedelta(hours=i, minutes=59),
        )
        for i in range(n)
    ]


class FakeClient:
    def get_klines(self, *_: Any, **__: Any) -> list[Kline]:
        return _klines(30)


class BuyWhenFlat(BaseStrategy):
    """Buys 1 unit while flat; holds once it has a position."""

    kind = "test"

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        if ctx.position.side == PositionSide.flat.value:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=Decimal("1"),
            )
        return None


class Exploding(BaseStrategy):
    kind = "test"

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        raise RuntimeError("boom")


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


def _engine(factory: Any, strategies: list[BaseStrategy]) -> TradingEngine:
    # Mirror startup seeding — every strategy gets a capital budget so the
    # allocation enforcer admits its orders.
    with factory() as session:
        for strat in strategies:
            set_allocation(session, strat.name, Decimal("100000"))
    return TradingEngine(
        session_factory=factory,
        client=FakeClient(),  # type: ignore[arg-type]
        strategies=strategies,  # default ExecutorRouter — Sim mode
    )


def test_tick_executes_strategy_order(db_engine: Any, factory: Any) -> None:
    strat = BuyWhenFlat("MA Cross", "BTCUSDT", market=Market.spot)
    eng = _engine(factory, [strat])
    eng.tick()
    with Session(db_engine) as s:
        trades = s.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].side == FillSide.buy.value


def test_tick_is_idempotent_when_strategy_holds(db_engine: Any, factory: Any) -> None:
    eng = _engine(factory, [BuyWhenFlat("MA Cross", "BTCUSDT")])
    eng.tick()  # buys
    eng.tick()  # holds — already long
    with Session(db_engine) as s:
        assert len(s.exec(select(Trade)).all()) == 1


def test_failing_strategy_does_not_abort_tick(db_engine: Any, factory: Any) -> None:
    eng = _engine(
        factory,
        [Exploding("Broken", "ETHUSDT"), BuyWhenFlat("Good", "BTCUSDT")],
    )
    eng.tick()  # must not raise
    with Session(db_engine) as s:
        trades = s.exec(select(Trade)).all()
    assert len(trades) == 1  # the healthy strategy still executed
    assert trades[0].strategy == "Good"


def test_register_adds_strategy(factory: Any) -> None:
    eng = _engine(factory, [])
    assert eng.strategies == []
    eng.register(BuyWhenFlat("MA Cross", "BTCUSDT"))
    assert len(eng.strategies) == 1


def test_start_and_stop(factory: Any) -> None:
    eng = _engine(factory, [])
    eng.start()
    eng.stop()  # must not raise


def test_stop_prevents_further_ticks(db_engine: Any, factory: Any) -> None:
    eng = _engine(factory, [BuyWhenFlat("MA Cross", "BTCUSDT")])
    eng.stop()  # graceful shutdown — no new tick may begin afterwards
    eng.tick()
    with Session(db_engine) as s:
        assert s.exec(select(Trade)).all() == []


def test_flatten_closes_open_positions(db_engine: Any, factory: Any) -> None:
    eng = _engine(factory, [BuyWhenFlat("MA Cross", "BTCUSDT")])
    eng.tick()  # opens a long position
    with Session(db_engine) as s:
        assert len(list_positions(s, strategy="MA Cross", open_only=True)) == 1

    closed = eng.flatten("MA Cross")
    assert closed == 1
    with Session(db_engine) as s:
        assert list_positions(s, strategy="MA Cross", open_only=True) == []

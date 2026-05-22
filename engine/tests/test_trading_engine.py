"""Tests for the TradingEngine tick loop and the strategy framework."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from trading.engine import TradingEngine
from trading.executors.base import Order
from trading.models import FillSide, PositionSide, Trade
from trading.portfolio import list_positions, set_allocation
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


def _venue_candles(n: int) -> list[VenueCandle]:
    # End at the current hour so the newest candle passes the staleness check.
    base = datetime.now(UTC).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=n - 1)
    return [
        VenueCandle(
            open_time=base + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for i in range(n)
    ]


class FakeVenue(Venue):
    """A venue that serves canned recent candles; the engine only reads data."""

    name = "fake"

    def instrument(self, symbol: str) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return _venue_candles(30)

    def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


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


def _engine(
    factory: Any,
    strategies: list[BaseStrategy],
    *,
    ai_resolver: Any = None,
) -> TradingEngine:
    # Mirror startup seeding — every strategy gets a capital budget so the
    # allocation enforcer admits its orders.
    with factory() as session:
        for strat in strategies:
            set_allocation(session, strat.name, Decimal("100000"))
    venue = FakeVenue()
    kwargs: dict[str, Any] = {}
    if ai_resolver is not None:
        kwargs["ai_resolver"] = ai_resolver
    return TradingEngine(
        session_factory=factory,
        venue_router=VenueRouter(builder=lambda *_: venue),
        strategies=strategies,  # default ExecutorRouter — Sim mode
        **kwargs,
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


def test_ai_strategy_paused_when_llm_spend_cap_reached(
    db_engine: Any, factory: Any
) -> None:
    """Once the daily LLM spend cap is hit, the engine skips AI strategies."""
    from ai.providers.base import Completion, LLMProvider
    from ai.usage import record_usage
    from appsettings.store import set_ai_spend_cap
    from strategies.ai_strategy import AIStrategy

    class CountingProvider(LLMProvider):
        name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, prompt: str, *, model: str | None = None) -> Completion:
            self.calls += 1
            return Completion(
                text='{"action": "hold", "confidence": 0.5, "reasoning": "x"}',
                provider=self.name,
                model="m",
                input_tokens=1,
                output_tokens=1,
            )

    provider = CountingProvider()
    strat = AIStrategy("AI BTC", "BTCUSDT")
    engine = _engine(
        factory, [strat], ai_resolver=lambda _s, _n: (provider, None)
    )
    with factory() as session:
        set_ai_spend_cap(session, Decimal("1"))
        # $3 already spent today — over the $1 cap.
        record_usage(
            session,
            provider="claude",
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
        )

    engine.tick()
    assert provider.calls == 0  # the paid LLM call was skipped


def test_ai_strategy_runs_when_under_the_cap(db_engine: Any, factory: Any) -> None:
    """Under the cap, the AI strategy ticks and its LLM usage is recorded."""
    from ai.providers.base import Completion, LLMProvider
    from ai.usage import LLMUsage
    from strategies.ai_strategy import AIStrategy

    class StubProvider(LLMProvider):
        name = "fake"

        def complete(self, prompt: str, *, model: str | None = None) -> Completion:
            return Completion(
                text='{"action": "hold", "confidence": 0.5, "reasoning": "x"}',
                provider=self.name,
                model=model or "m",
                input_tokens=10,
                output_tokens=5,
            )

    provider = StubProvider()
    engine = _engine(
        factory,
        [AIStrategy("AI BTC", "BTCUSDT")],
        ai_resolver=lambda _s, _n: (provider, "stub-model"),
    )
    engine.tick()
    with factory() as session:
        rows = session.exec(select(LLMUsage)).all()
    assert len(rows) == 1
    assert rows[0].strategy == "AI BTC"
    assert rows[0].model == "stub-model"

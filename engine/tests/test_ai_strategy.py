"""Tests for AIStrategy — hermetic, fake LLM provider."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai.providers.base import LLMError, LLMProvider
from marketdata.models import Candle
from strategies.ai_strategy import AIStrategy
from strategies.base import StrategyContext
from trading.models import FillSide, Position, PositionSide


class FakeProvider(LLMProvider):
    """LLM provider returning a canned response (or raising)."""

    name = "fake"

    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        if self._raises:
            raise LLMError("provider unavailable")
        return self._text


def _candles(n: int = 5) -> list[Candle]:
    base = datetime(2024, 5, 20, tzinfo=UTC)
    return [
        Candle(
            market="spot",
            symbol="BTCUSDT",
            interval="1h",
            open_time=base + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("1"),
            close_time=base + timedelta(hours=i, minutes=59),
        )
        for i in range(n)
    ]


def _ctx(position: Position) -> StrategyContext:
    return StrategyContext(
        candles=_candles(),
        position=position,
        allocation=Decimal("1000"),
        price=Decimal("100"),
    )


def _flat() -> Position:
    return Position(strategy="AI", market="spot", symbol="BTCUSDT")


def _long() -> Position:
    return Position(
        strategy="AI",
        market="spot",
        symbol="BTCUSDT",
        side=PositionSide.long.value,
        qty=Decimal("5"),
        entry_price=Decimal("90"),
    )


def _strategy(text: str = "", *, raises: bool = False) -> AIStrategy:
    return AIStrategy("AI BTC", "BTCUSDT", provider=FakeProvider(text, raises=raises))


def test_buy_decision_opens_a_position() -> None:
    order = _strategy('{"action": "buy", "confidence": 0.9, "reasoning": "up"}').evaluate(
        _ctx(_flat())
    )
    assert order is not None
    assert order.side is FillSide.buy
    assert order.quantity == Decimal("10")  # allocation 1000 / price 100


def test_sell_decision_closes_a_position() -> None:
    order = _strategy('{"action": "sell", "confidence": 0.7, "reasoning": "down"}').evaluate(
        _ctx(_long())
    )
    assert order is not None
    assert order.side is FillSide.sell
    assert order.quantity == Decimal("5")  # the whole position


def test_hold_decision_does_nothing() -> None:
    assert _strategy('{"action": "hold", "confidence": 0.5}').evaluate(_ctx(_flat())) is None


def test_buy_when_already_long_does_nothing() -> None:
    order = _strategy('{"action": "buy", "confidence": 0.9}').evaluate(_ctx(_long()))
    assert order is None  # state-based — no doubling up


def test_llm_failure_holds() -> None:
    assert _strategy(raises=True).evaluate(_ctx(_flat())) is None


def test_insufficient_history_holds() -> None:
    strat = _strategy('{"action": "buy", "confidence": 0.9}')
    ctx = StrategyContext(
        candles=_candles(1),
        position=_flat(),
        allocation=Decimal("1000"),
        price=Decimal("100"),
    )
    assert strat.evaluate(ctx) is None

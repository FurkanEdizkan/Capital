"""Tests for the MA crossover strategy — hermetic, synthetic candles."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from marketdata.models import Candle
from strategies.base import StrategyContext
from strategies.ma_cross import MACrossStrategy
from trading.models import FillSide, Position, PositionSide


def _candles(closes: list[float]) -> list[Candle]:
    base = datetime(2024, 5, 20, tzinfo=UTC)
    return [
        Candle(
            market="spot",
            symbol="BTCUSDT",
            interval="1h",
            open_time=base + timedelta(hours=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=Decimal("1"),
            close_time=base + timedelta(hours=i, minutes=59),
        )
        for i, c in enumerate(closes)
    ]


def _ctx(closes: list[float], position: Position, allocation: str = "1000") -> StrategyContext:
    candles = _candles(closes)
    return StrategyContext(
        candles=candles,
        position=position,
        allocation=Decimal(allocation),
        price=Decimal("100"),
    )


def _flat() -> Position:
    return Position(strategy="S", market="spot", symbol="BTCUSDT")


def _long(qty: str = "0.5") -> Position:
    return Position(
        strategy="S",
        market="spot",
        symbol="BTCUSDT",
        side=PositionSide.long.value,
        qty=Decimal(qty),
        entry_price=Decimal("90"),
    )


RISING = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
FALLING = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]


def test_fast_ge_slow_rejected() -> None:
    with pytest.raises(ValueError):
        MACrossStrategy("S", "BTCUSDT", fast=10, slow=10)


def test_not_enough_candles_holds() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    assert strat.evaluate(_ctx([1, 2, 3], _flat())) is None


def test_enters_long_on_uptrend() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    order = strat.evaluate(_ctx(RISING, _flat()))
    assert order is not None
    assert order.side is FillSide.buy
    assert order.quantity == Decimal("10")  # allocation 1000 / price 100


def test_exits_long_on_downtrend() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    order = strat.evaluate(_ctx(FALLING, _long("0.5")))
    assert order is not None
    assert order.side is FillSide.sell
    assert order.quantity == Decimal("0.5")  # closes the whole position


def test_holds_when_already_long_on_uptrend() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    assert strat.evaluate(_ctx(RISING, _long())) is None


def test_holds_when_flat_on_downtrend() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    assert strat.evaluate(_ctx(FALLING, _flat())) is None


def test_no_entry_without_allocation() -> None:
    strat = MACrossStrategy("S", "BTCUSDT", fast=3, slow=5)
    assert strat.evaluate(_ctx(RISING, _flat(), allocation="0")) is None

"""Tests for the Phase 3 default strategies — RSI, MACD, Bollinger, DCA.

Hermetic: every strategy is fed synthetic candles, never the network.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from marketdata.models import Candle
from strategies.base import StrategyContext
from strategies.bollinger import BollingerStrategy
from strategies.dca import DCAStrategy
from strategies.macd import MACDStrategy
from strategies.rsi import RSIStrategy
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


def _ctx(
    closes: list[float], position: Position, *, allocation: str = "1000", price: str = "100"
) -> StrategyContext:
    return StrategyContext(
        candles=_candles(closes),
        position=position,
        allocation=Decimal(allocation),
        price=Decimal(price),
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


RISING = list(range(1, 60))
FALLING = list(range(60, 1, -1))
PEAKED = list(range(1, 45)) + list(range(45, 1, -1))  # rises, then clearly falls
BALANCED = [10, 11] * 12  # alternating → RSI ≈ 50


# --- RSI -------------------------------------------------------------------

def test_rsi_rejects_bad_thresholds() -> None:
    with pytest.raises(ValueError):
        RSIStrategy("S", "BTCUSDT", oversold=Decimal(70), overbought=Decimal(30))


def test_rsi_holds_without_history() -> None:
    assert RSIStrategy("S", "BTCUSDT").evaluate(_ctx([1, 2, 3], _flat())) is None


def test_rsi_buys_when_oversold() -> None:
    order = RSIStrategy("S", "BTCUSDT").evaluate(_ctx(FALLING, _flat()))
    assert order is not None and order.side is FillSide.buy
    assert order.quantity == Decimal(10)  # allocation 1000 / price 100


def test_rsi_sells_when_overbought() -> None:
    order = RSIStrategy("S", "BTCUSDT").evaluate(_ctx(RISING, _long("0.5")))
    assert order is not None and order.side is FillSide.sell
    assert order.quantity == Decimal("0.5")


def test_rsi_holds_in_the_neutral_band() -> None:
    assert RSIStrategy("S", "BTCUSDT").evaluate(_ctx(BALANCED, _flat())) is None


# --- MACD ------------------------------------------------------------------

def test_macd_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError):
        MACDStrategy("S", "BTCUSDT", fast=26, slow=26)


def test_macd_holds_without_history() -> None:
    assert MACDStrategy("S", "BTCUSDT").evaluate(_ctx(RISING[:20], _flat())) is None


def test_macd_buys_on_uptrend() -> None:
    order = MACDStrategy("S", "BTCUSDT").evaluate(_ctx(RISING, _flat()))
    assert order is not None and order.side is FillSide.buy


def test_macd_sells_on_downtrend() -> None:
    order = MACDStrategy("S", "BTCUSDT").evaluate(_ctx(PEAKED, _long("0.5")))
    assert order is not None and order.side is FillSide.sell


# --- Bollinger -------------------------------------------------------------

def test_bollinger_holds_without_history() -> None:
    assert BollingerStrategy("S", "BTCUSDT").evaluate(_ctx([100] * 5, _flat())) is None


def test_bollinger_buys_on_upper_break() -> None:
    order = BollingerStrategy("S", "BTCUSDT").evaluate(_ctx([100] * 19 + [200], _flat()))
    assert order is not None and order.side is FillSide.buy


def test_bollinger_sells_below_the_middle_band() -> None:
    order = BollingerStrategy("S", "BTCUSDT").evaluate(_ctx([100] * 19 + [50], _long("0.5")))
    assert order is not None and order.side is FillSide.sell


def test_bollinger_holds_on_flat_series() -> None:
    assert BollingerStrategy("S", "BTCUSDT").evaluate(_ctx([100] * 20, _flat())) is None


# --- DCA -------------------------------------------------------------------

def test_dca_rejects_bad_tranche() -> None:
    with pytest.raises(ValueError):
        DCAStrategy("S", "BTCUSDT", tranche=Decimal(2))


def test_dca_buys_one_tranche_when_flat() -> None:
    order = DCAStrategy("S", "BTCUSDT").evaluate(_ctx([], _flat()))
    assert order is not None and order.side is FillSide.buy
    assert order.quantity == Decimal(1)  # 10% of 1000 / price 100


def test_dca_stops_once_fully_deployed() -> None:
    assert DCAStrategy("S", "BTCUSDT").evaluate(_ctx([], _long("10"))) is None


def test_dca_holds_without_allocation() -> None:
    assert DCAStrategy("S", "BTCUSDT").evaluate(_ctx([], _flat(), allocation="0")) is None

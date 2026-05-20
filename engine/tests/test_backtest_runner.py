"""Tests for the backtest runner — hermetic, synthetic candles."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backtest.runner import FeeModel, run_backtest
from exchange.client import Market
from marketdata.models import Candle
from strategies.base import BaseStrategy, StrategyContext
from strategies.ma_cross import MACrossStrategy
from trading.executors.base import Order
from trading.models import FillSide, PositionSide

_NO_COST = FeeModel(slippage_bps=Decimal(0), fee_rate=Decimal(0))


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


class BuyAndHold(BaseStrategy):
    """Buys the full allocation once, then holds."""

    kind = "test"

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        if ctx.position.side == PositionSide.flat.value and ctx.allocation > 0:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,
            )
        return None


class DoNothing(BaseStrategy):
    kind = "test"

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        return None


def test_buy_and_hold_tracks_price() -> None:
    # Price doubles → cost-free buy-and-hold equity doubles.
    result = run_backtest(
        BuyAndHold("S", "BTCUSDT"),
        _candles([100, 120, 150, 200]),
        initial_capital=Decimal("1000"),
        fees=_NO_COST,
    )
    assert result.final_equity == Decimal("2000")
    assert result.net_pnl == Decimal("1000")
    assert len(result.trades) == 1
    assert result.metrics is not None
    assert result.metrics.total_return_pct == Decimal("100")


def test_fees_reduce_returns() -> None:
    candles = _candles([100, 120, 150, 200])
    free = run_backtest(
        BuyAndHold("S", "BTCUSDT"), candles, initial_capital=Decimal("1000"), fees=_NO_COST
    )
    costed = run_backtest(
        BuyAndHold("S", "BTCUSDT"),
        candles,
        initial_capital=Decimal("1000"),
        fees=FeeModel(),  # default slippage + fee
    )
    assert costed.final_equity < free.final_equity
    assert costed.total_fees > 0


def test_funding_costs_a_held_position() -> None:
    candles = _candles([100, 120, 150, 200])
    free = run_backtest(
        BuyAndHold("S", "BTCUSDT"), candles, initial_capital=Decimal("1000"), fees=_NO_COST
    )
    funded = run_backtest(
        BuyAndHold("S", "BTCUSDT"),
        candles,
        initial_capital=Decimal("1000"),
        fees=FeeModel(slippage_bps=Decimal(0), fee_rate=Decimal(0), funding_rate=Decimal("0.001")),
    )
    assert funded.final_equity < free.final_equity


def test_no_signal_leaves_equity_flat() -> None:
    result = run_backtest(
        DoNothing("S", "BTCUSDT"),
        _candles([100, 110, 90, 105]),
        initial_capital=Decimal("1000"),
        fees=FeeModel(),
    )
    assert result.trades == []
    assert result.final_equity == Decimal("1000")
    assert result.net_pnl == Decimal("0")


def test_empty_candles_is_a_no_op() -> None:
    result = run_backtest(
        BuyAndHold("S", "BTCUSDT"), [], initial_capital=Decimal("1000")
    )
    assert result.final_equity == Decimal("1000")
    assert result.equity_curve == []
    assert result.metrics is not None
    assert result.metrics.total_return_pct == Decimal("0")


def test_round_trip_books_a_winning_trade() -> None:
    # Rise (MA cross enters long) then fall (it closes) at a higher price.
    strat = MACrossStrategy("S", "BTCUSDT", market=Market.spot, fast=2, slow=3)
    candles = _candles([10, 11, 12, 14, 17, 21, 26, 20, 14, 9])
    result = run_backtest(strat, candles, initial_capital=Decimal("1000"), fees=_NO_COST)
    assert result.metrics is not None
    # The strategy opened and closed at least once.
    closing = [t for t in result.trades if t.realized_pnl != 0]
    assert len(closing) >= 1
    assert result.metrics.wins + result.metrics.losses == len(closing)


def test_max_drawdown_is_measured() -> None:
    # Buy at the top, ride it down — a clear drawdown.
    result = run_backtest(
        BuyAndHold("S", "BTCUSDT"),
        _candles([100, 80, 60, 50]),
        initial_capital=Decimal("1000"),
        fees=_NO_COST,
    )
    assert result.metrics is not None
    assert result.metrics.max_drawdown_pct > 0
    assert result.final_equity < Decimal("1000")

"""Backtest runner — replay a strategy over historical candles.

A backtest is a pure in-memory simulation: it never touches the database or
an executor (those serve live paper trading). Each bar, the strategy is asked
for an order; fills are modelled with a configurable **slippage + fee** model,
and futures positions accrue **funding** per bar. The result carries the
equity curve, the trade log and headline metrics (return, win rate, max
drawdown, Sharpe).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from marketdata.models import Candle
from strategies.base import BaseStrategy, StrategyContext
from trading.models import FillSide, Position, PositionSide

_BPS = Decimal(10_000)


@dataclass
class FeeModel:
    """How fills are penalised so backtest results are not optimistic."""

    slippage_bps: Decimal = Decimal("2")  # adverse price move applied to fills
    fee_rate: Decimal = Decimal("0.001")  # taker commission, fraction of notional
    funding_rate: Decimal = Decimal("0")  # per-bar funding (futures), fraction


@dataclass
class BacktestTrade:
    """One simulated fill."""

    time: datetime
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal


@dataclass
class BacktestMetrics:
    """Headline performance metrics for a completed backtest."""

    total_return_pct: Decimal
    win_rate_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal  # per-bar Sharpe ratio (mean / stdev of bar returns)
    trades: int
    wins: int
    losses: int


@dataclass
class BacktestResult:
    """Everything a backtest produces."""

    initial_capital: Decimal
    final_equity: Decimal
    net_pnl: Decimal
    total_fees: Decimal
    equity_curve: list[tuple[datetime, Decimal]] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)
    metrics: BacktestMetrics | None = None


@dataclass
class _SimPosition:
    """In-memory signed position with volume-weighted entry and realized PnL."""

    qty: Decimal = Decimal(0)  # signed — long positive, short negative
    entry_price: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)

    def apply(self, side: FillSide, qty: Decimal, price: Decimal) -> Decimal:
        """Apply a fill; return the realized PnL booked by it.

        Mirrors `trading.portfolio.apply_fill` — VWAP entry on opening/adding,
        PnL booked on reducing/closing, the entry reset on a flip past flat.
        """
        delta = qty if side is FillSide.buy else -qty
        signed = self.qty
        new_signed = signed + delta
        booked = Decimal(0)

        same_direction = signed == 0 or (signed > 0) == (delta > 0)
        if same_direction:
            prev_abs = abs(signed)
            self.entry_price = (
                prev_abs * self.entry_price + qty * price
            ) / (prev_abs + qty)
        else:
            closed = min(qty, abs(signed))
            direction = Decimal(1) if signed > 0 else Decimal(-1)
            booked = (price - self.entry_price) * closed * direction
            self.realized_pnl += booked
            if abs(delta) > abs(signed):
                self.entry_price = price  # flipped past flat
            elif new_signed == 0:
                self.entry_price = Decimal(0)

        self.qty = new_signed
        return booked

    def as_model(self, strategy: str, market: str, symbol: str) -> Position:
        """A read-only `Position` view for the strategy's context."""
        side = (
            PositionSide.long.value
            if self.qty > 0
            else PositionSide.short.value
            if self.qty < 0
            else PositionSide.flat.value
        )
        return Position(
            strategy=strategy,
            market=market,
            symbol=symbol,
            side=side,
            qty=abs(self.qty),
            entry_price=self.entry_price,
        )

    def unrealized(self, price: Decimal) -> Decimal:
        """Mark-to-market PnL of the open portion at `price`."""
        return (price - self.entry_price) * self.qty


def _stdev(values: list[Decimal]) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    mean = sum(values, Decimal(0)) / Decimal(len(values))
    variance = sum(((v - mean) ** 2 for v in values), Decimal(0)) / Decimal(len(values))
    return variance.sqrt()


def _metrics(
    initial: Decimal,
    equity_curve: list[tuple[datetime, Decimal]],
    trades: list[BacktestTrade],
) -> BacktestMetrics:
    final = equity_curve[-1][1] if equity_curve else initial
    total_return = (final - initial) / initial * Decimal(100) if initial > 0 else Decimal(0)

    # Win rate over fills that actually closed part of a position.
    closing = [t for t in trades if t.realized_pnl != 0]
    wins = sum(1 for t in closing if t.realized_pnl > 0)
    losses = len(closing) - wins
    win_rate = Decimal(wins) / Decimal(len(closing)) * Decimal(100) if closing else Decimal(0)

    # Max drawdown — deepest peak-to-trough decline of the equity curve.
    peak = initial
    max_dd = Decimal(0)
    for _, equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * Decimal(100))

    # Per-bar Sharpe — mean / stdev of bar-to-bar equity returns.
    returns: list[Decimal] = []
    prev = initial
    for _, equity in equity_curve:
        if prev > 0:
            returns.append((equity - prev) / prev)
        prev = equity
    sharpe = Decimal(0)
    if returns:
        mean = sum(returns, Decimal(0)) / Decimal(len(returns))
        sd = _stdev(returns)
        if sd > 0:
            sharpe = mean / sd

    return BacktestMetrics(
        total_return_pct=total_return,
        win_rate_pct=win_rate,
        max_drawdown_pct=max_dd,
        sharpe=sharpe,
        trades=len(trades),
        wins=wins,
        losses=losses,
    )


def run_backtest(
    strategy: BaseStrategy,
    candles: list[Candle],
    *,
    initial_capital: Decimal,
    fees: FeeModel | None = None,
) -> BacktestResult:
    """Replay `strategy` bar-by-bar over `candles`.

    `initial_capital` is the strategy's allocation for the run. Returns a
    `BacktestResult` with the equity curve, trade log and metrics.
    """
    fees = fees or FeeModel()
    initial_capital = Decimal(initial_capital)
    pos = _SimPosition()
    trades: list[BacktestTrade] = []
    equity_curve: list[tuple[datetime, Decimal]] = []
    total_fees = Decimal(0)
    total_funding = Decimal(0)

    for i, candle in enumerate(candles):
        price = candle.close

        ctx = StrategyContext(
            candles=candles[: i + 1],
            position=pos.as_model(strategy.name, strategy.market.value, strategy.symbol),
            allocation=initial_capital,
            price=price,
        )
        order = strategy.evaluate(ctx)
        if order is not None and order.quantity > 0:
            # Slippage moves the fill price against us.
            slip = fees.slippage_bps / _BPS
            fill_price = (
                price * (Decimal(1) + slip)
                if order.side is FillSide.buy
                else price * (Decimal(1) - slip)
            )
            fee = fill_price * order.quantity * fees.fee_rate
            total_fees += fee
            booked = pos.apply(order.side, order.quantity, fill_price)
            trades.append(
                BacktestTrade(
                    time=candle.open_time,
                    side=order.side.value,
                    quantity=order.quantity,
                    price=fill_price,
                    fee=fee,
                    realized_pnl=booked,
                )
            )

        # Futures funding accrues each bar an exposure is held.
        if pos.qty != 0 and fees.funding_rate != 0:
            total_funding += abs(pos.qty) * price * fees.funding_rate

        equity = (
            initial_capital
            + pos.realized_pnl
            + pos.unrealized(price)
            - total_fees
            - total_funding
        )
        equity_curve.append((candle.open_time, equity))

    final_equity = equity_curve[-1][1] if equity_curve else initial_capital
    return BacktestResult(
        initial_capital=initial_capital,
        final_equity=final_equity,
        net_pnl=final_equity - initial_capital,
        total_fees=total_fees,
        equity_curve=equity_curve,
        trades=trades,
        metrics=_metrics(initial_capital, equity_curve, trades),
    )

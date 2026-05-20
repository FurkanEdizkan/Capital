"""Accounting — portfolio PnL, fees and equity-history snapshots.

Realized PnL is booked gross on each position; fees accrue separately. The
headline **net PnL is always reported net of fees** (and, once futures land,
funding). Equity = total capital allocated + net PnL.
"""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlmodel import Session, select

from trading.models import EquitySnapshot, Position, PositionSide, StrategyAllocation
from trading.portfolio import unrealized_pnl

MarkPrices = dict[str, Decimal]


class StrategySummary(BaseModel):
    strategy: str
    allocated: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    open_positions: int


class PortfolioSummary(BaseModel):
    total_allocated: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    equity: Decimal
    deployed_capital: Decimal
    idle_capital: Decimal
    open_positions: int
    strategies: list[StrategySummary]


def _is_open(pos: Position) -> bool:
    return pos.side != PositionSide.flat.value and pos.qty > 0


def strategy_summary(
    session: Session, strategy: str, mark_prices: MarkPrices
) -> StrategySummary:
    positions = list(
        session.exec(select(Position).where(Position.strategy == strategy)).all()
    )
    alloc = session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == strategy)
    ).first()

    realized = sum((p.realized_pnl for p in positions), Decimal(0))
    fees = sum((p.fees_paid for p in positions), Decimal(0))
    unreal = sum(
        (
            unrealized_pnl(p, mark_prices.get(p.symbol, p.entry_price))
            for p in positions
            if _is_open(p)
        ),
        Decimal(0),
    )
    return StrategySummary(
        strategy=strategy,
        allocated=alloc.allocated if alloc else Decimal(0),
        realized_pnl=realized,
        unrealized_pnl=unreal,
        fees=fees,
        net_pnl=realized + unreal - fees,
        open_positions=sum(1 for p in positions if _is_open(p)),
    )


def portfolio_summary(session: Session, mark_prices: MarkPrices) -> PortfolioSummary:
    """Aggregate accounting across every strategy."""
    strategies = sorted(
        {p.strategy for p in session.exec(select(Position)).all()}
        | {a.strategy for a in session.exec(select(StrategyAllocation)).all()}
    )
    summaries = [strategy_summary(session, s, mark_prices) for s in strategies]

    total_allocated = sum((s.allocated for s in summaries), Decimal(0))
    realized = sum((s.realized_pnl for s in summaries), Decimal(0))
    unreal = sum((s.unrealized_pnl for s in summaries), Decimal(0))
    fees = sum((s.fees for s in summaries), Decimal(0))
    net = realized + unreal - fees

    deployed = sum(
        (
            p.qty * p.entry_price
            for p in session.exec(select(Position)).all()
            if _is_open(p)
        ),
        Decimal(0),
    )
    return PortfolioSummary(
        total_allocated=total_allocated,
        realized_pnl=realized,
        unrealized_pnl=unreal,
        total_fees=fees,
        net_pnl=net,
        equity=total_allocated + net,
        deployed_capital=deployed,
        idle_capital=max(total_allocated - deployed, Decimal(0)),
        open_positions=sum(s.open_positions for s in summaries),
        strategies=summaries,
    )


def record_equity_snapshot(
    session: Session, mark_prices: MarkPrices
) -> EquitySnapshot:
    """Compute the current portfolio summary and append an equity snapshot."""
    s = portfolio_summary(session, mark_prices)
    snap = EquitySnapshot(
        ts=datetime.now(UTC).replace(tzinfo=None),
        equity=s.equity,
        realized_pnl=s.realized_pnl,
        unrealized_pnl=s.unrealized_pnl,
        fees=s.total_fees,
        net_pnl=s.net_pnl,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def equity_history(session: Session, limit: int = 500) -> list[EquitySnapshot]:
    """Recent equity snapshots, oldest-first (for the dashboard curve)."""
    rows = session.exec(
        select(EquitySnapshot).order_by(EquitySnapshot.ts.desc()).limit(limit)  # type: ignore[attr-defined]
    ).all()
    return list(reversed(rows))

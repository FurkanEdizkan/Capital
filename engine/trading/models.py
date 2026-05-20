"""Trading database models — per-strategy positions and capital allocations.

The `Position` table is the **attribution sub-ledger**: the exchange holds one
account-level position per symbol, but each strategy gets its own Position row
so per-strategy size, entry and PnL stay correct even when several strategies
trade the same symbol. See plan: Architecture / Position attribution.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

_AMT = {"max_digits": 28, "decimal_places": 10}


class PositionSide(StrEnum):
    long = "long"
    short = "short"
    flat = "flat"


class FillSide(StrEnum):
    buy = "buy"
    sell = "sell"


class StrategyAllocation(SQLModel, table=True):
    """Per-strategy config row — capital budget and lifecycle state.

    `allocated` is the quote-currency budget the engine caps the strategy's
    exposure to; `enabled` gates whether the engine ticks it for new entries
    (a disabled strategy keeps its open positions — see trading/lifecycle.py).
    """

    __tablename__ = "strategy_allocation"

    id: int | None = Field(default=None, primary_key=True)
    strategy: str = Field(unique=True, index=True, max_length=64)
    allocated: Decimal = Field(default=Decimal(0), **_AMT)
    enabled: bool = Field(default=True)


class Position(SQLModel, table=True):
    """One strategy's position in one symbol/market — the attribution row.

    `qty` is always >= 0; `side` gives the direction. `realized_pnl` and
    `fees_paid` accumulate over the position's lifetime (the row is kept after
    a position goes flat so cumulative PnL is preserved).
    """

    __tablename__ = "position"
    __table_args__ = (
        UniqueConstraint("strategy", "market", "symbol", name="uq_position"),
    )

    id: int | None = Field(default=None, primary_key=True)
    strategy: str = Field(index=True, max_length=64)
    market: str = Field(max_length=8)
    symbol: str = Field(index=True, max_length=24)
    side: str = Field(default=PositionSide.flat.value, max_length=8)
    qty: Decimal = Field(default=Decimal(0), **_AMT)
    entry_price: Decimal = Field(default=Decimal(0), **_AMT)
    realized_pnl: Decimal = Field(default=Decimal(0), **_AMT)
    fees_paid: Decimal = Field(default=Decimal(0), **_AMT)
    opened_at: datetime | None = None
    updated_at: datetime | None = None


class Trade(SQLModel, table=True):
    """An executed fill — the transaction-log row, attributed to a strategy.

    `realized_pnl` is the PnL booked *by this fill* (0 for opening/adding fills,
    non-zero when it reduces or closes a position).
    """

    __tablename__ = "trade"

    id: int | None = Field(default=None, primary_key=True)
    strategy: str = Field(index=True, max_length=64)
    market: str = Field(max_length=8)
    symbol: str = Field(index=True, max_length=24)
    side: str = Field(max_length=8)
    quantity: Decimal = Field(**_AMT)
    price: Decimal = Field(**_AMT)
    fee: Decimal = Field(default=Decimal(0), **_AMT)
    realized_pnl: Decimal = Field(default=Decimal(0), **_AMT)
    mode: str = Field(default="sim", max_length=8)
    executed_at: datetime = Field(index=True)


class EquitySnapshot(SQLModel, table=True):
    """A point-in-time snapshot of portfolio equity — powers the equity curve."""

    __tablename__ = "equity_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(index=True)
    equity: Decimal = Field(**_AMT)
    realized_pnl: Decimal = Field(**_AMT)
    unrealized_pnl: Decimal = Field(**_AMT)
    fees: Decimal = Field(**_AMT)
    net_pnl: Decimal = Field(**_AMT)

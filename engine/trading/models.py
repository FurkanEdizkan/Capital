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
    """The capital budget (quote currency) assigned to one strategy."""

    __tablename__ = "strategy_allocation"

    id: int | None = Field(default=None, primary_key=True)
    strategy: str = Field(unique=True, index=True, max_length=64)
    allocated: Decimal = Field(default=Decimal(0), **_AMT)


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

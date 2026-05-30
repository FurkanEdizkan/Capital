"""AI signals — pending decisions awaiting operator confirmation.

When an AI strategy runs in *notify* mode (the safe default), its decision is
not executed automatically: a row is written here and the operator is notified
(Telegram + the Dashboard). Confirming a signal runs the order through the same
executor + risk path as a manual order; dismissing it leaves it on record.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, Session, SQLModel, select

_AMT = {"max_digits": 28, "decimal_places": 10}
_PRICE = {"max_digits": 24, "decimal_places": 8}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SignalStatus(StrEnum):
    pending = "pending"
    executed = "executed"
    dismissed = "dismissed"


class AISignal(SQLModel, table=True):
    """One AI decision surfaced to the operator for confirmation."""

    __tablename__ = "ai_signal"

    id: int | None = Field(default=None, primary_key=True)
    strategy: str = Field(index=True, max_length=64)
    symbol: str = Field(index=True, max_length=24)
    market: str = Field(default="spot", max_length=8)
    action: str = Field(max_length=8)
    confidence: Decimal = Field(default=Decimal(0), **_AMT)
    reasoning: str = Field(default="")
    reference_price: Decimal = Field(default=Decimal(0), **_PRICE)
    quantity: Decimal = Field(default=Decimal(0), **_PRICE)
    status: str = Field(default=SignalStatus.pending.value, max_length=12, index=True)
    created_at: datetime = Field(index=True)


def record_signal(
    session: Session,
    *,
    strategy: str,
    symbol: str,
    market: str,
    action: str,
    confidence: Decimal,
    reasoning: str,
    reference_price: Decimal,
    quantity: Decimal,
) -> AISignal:
    """Insert one pending AI signal."""
    row = AISignal(
        strategy=strategy,
        symbol=symbol,
        market=market,
        action=action,
        confidence=confidence,
        reasoning=reasoning,
        reference_price=reference_price,
        quantity=quantity,
        created_at=_utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def recent_signals(
    session: Session, *, status: str | None = None, limit: int = 50
) -> list[AISignal]:
    """Recent signals, newest first — optionally filtered by status."""
    stmt = select(AISignal)
    if status:
        stmt = stmt.where(AISignal.status == status)
    stmt = stmt.order_by(AISignal.created_at.desc()).limit(limit)  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())

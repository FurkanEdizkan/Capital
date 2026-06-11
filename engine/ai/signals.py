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

from config import settings
from trading.executor_router import ExecutorRouter
from trading.executors.base import Order
from trading.models import FillSide
from trading.portfolio import get_or_create_position
from trading.risk import RiskManager
from trading.venue_router import VenueRouter

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
    symbol: str = Field(index=True, max_length=80)  # Polymarket token ids are long
    venue: str = Field(default="binance", max_length=24)
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
    venue: str = "binance",
) -> AISignal:
    """Insert one pending AI signal."""
    row = AISignal(
        strategy=strategy,
        symbol=symbol,
        venue=venue,
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


class SignalBlockedError(Exception):
    """The risk manager refused the signal's order (size cap or kill switch)."""


def execute_signal(
    session: Session,
    signal: AISignal,
    venues: VenueRouter,
    *,
    executor_router: ExecutorRouter | None = None,
) -> AISignal:
    """Execute a pending signal through the shared risk + executor path.

    Re-prices at execution time and re-runs the risk gate, so a stale or
    risk-blocked signal cannot slip through. Marks the signal `executed`.
    Shared by the operator-confirm API endpoint and the council's auto mode.

    Raises `VenueError` (pricing failed), `SignalBlockedError` (risk refused)
    or `ExecutionError` (the executor rejected the order).
    """
    price = venues.resolve(session, venue=signal.venue).price(signal.symbol)
    position = get_or_create_position(
        session, signal.strategy, signal.market, signal.symbol
    )
    order = Order(
        strategy=signal.strategy,
        market=signal.market,
        symbol=signal.symbol,
        side=FillSide(signal.action),
        quantity=signal.quantity,
    )
    reviewed = RiskManager.from_settings(settings).review(
        session, order, position, price
    )
    if reviewed is None:
        raise SignalBlockedError(
            "order blocked by the risk manager (size cap or kill switch)"
        )
    executor = (executor_router or ExecutorRouter()).resolve(
        session, venue=signal.venue
    )
    executor.execute(session, reviewed, reference_price=price)
    signal.status = SignalStatus.executed.value
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return signal

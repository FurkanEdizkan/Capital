"""Portfolio — the position-attribution sub-ledger.

`apply_fill` is the heart of it: every executed fill is attributed to the
strategy that triggered it and folded into *that strategy's* position, with
realized PnL booked when a position is reduced or closed. Average entry price
is volume-weighted; flipping past flat opens the new leg at the fill price.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, select

from trading.executors.base import Fill, Order
from trading.models import FillSide, Position, PositionSide, StrategyAllocation, Trade


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _signed_qty(pos: Position) -> Decimal:
    """Position size as a signed number — long positive, short negative."""
    if pos.side == PositionSide.long.value:
        return pos.qty
    if pos.side == PositionSide.short.value:
        return -pos.qty
    return Decimal(0)


def get_or_create_position(
    session: Session, strategy: str, market: str, symbol: str
) -> Position:
    pos = session.exec(
        select(Position).where(
            Position.strategy == strategy,
            Position.market == market,
            Position.symbol == symbol,
        )
    ).first()
    if pos is None:
        pos = Position(strategy=strategy, market=market, symbol=symbol)
        session.add(pos)
        session.commit()
        session.refresh(pos)
    return pos


def apply_fill(
    session: Session,
    *,
    strategy: str,
    market: str,
    symbol: str,
    side: FillSide | str,
    qty: Decimal,
    price: Decimal,
    fee: Decimal = Decimal(0),
) -> Position:
    """Attribute a fill to `strategy`'s position and update it.

    Raises `ValueError` on a non-positive quantity.
    """
    side = FillSide(side)
    qty, price, fee = Decimal(qty), Decimal(price), Decimal(fee)
    if qty <= 0:
        raise ValueError("fill quantity must be positive")

    pos = get_or_create_position(session, strategy, market, symbol)
    signed = _signed_qty(pos)
    delta = qty if side is FillSide.buy else -qty
    new_signed = signed + delta
    pos.fees_paid += fee

    same_direction = signed == 0 or (signed > 0) == (delta > 0)
    if same_direction:
        # Opening or adding — volume-weighted average entry.
        prev_abs = abs(signed)
        pos.entry_price = (prev_abs * pos.entry_price + qty * price) / (prev_abs + qty)
    else:
        # Reducing / closing / flipping — realize PnL on the closed portion.
        closed = min(qty, abs(signed))
        direction = Decimal(1) if signed > 0 else Decimal(-1)
        pos.realized_pnl += (price - pos.entry_price) * closed * direction
        if abs(delta) > abs(signed):
            pos.entry_price = price  # flipped past flat — new leg opens here
        elif new_signed == 0:
            pos.entry_price = Decimal(0)

    pos.qty = abs(new_signed)
    pos.side = (
        PositionSide.long.value
        if new_signed > 0
        else PositionSide.short.value
        if new_signed < 0
        else PositionSide.flat.value
    )
    now = _utcnow()
    pos.opened_at = None if new_signed == 0 else (pos.opened_at or now)
    pos.updated_at = now

    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


def unrealized_pnl(pos: Position, mark_price: Decimal) -> Decimal:
    """Mark-to-market PnL of the open portion at `mark_price`."""
    if pos.side == PositionSide.flat.value or pos.qty == 0:
        return Decimal(0)
    direction = Decimal(1) if pos.side == PositionSide.long.value else Decimal(-1)
    return (Decimal(mark_price) - pos.entry_price) * pos.qty * direction


def list_positions(
    session: Session, *, strategy: str | None = None, open_only: bool = False
) -> list[Position]:
    query = select(Position)
    if strategy is not None:
        query = query.where(Position.strategy == strategy)
    if open_only:
        query = query.where(Position.side != PositionSide.flat.value)
    return list(session.exec(query).all())


# -- capital allocation -----------------------------------------------------

def get_allocation(session: Session, strategy: str) -> Decimal:
    row = session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == strategy)
    ).first()
    return row.allocated if row else Decimal(0)


def set_allocation(
    session: Session, strategy: str, amount: Decimal
) -> StrategyAllocation:
    row = session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == strategy)
    ).first()
    if row is None:
        row = StrategyAllocation(strategy=strategy, allocated=Decimal(amount))
    else:
        row.allocated = Decimal(amount)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_allocations(session: Session) -> list[StrategyAllocation]:
    return list(session.exec(select(StrategyAllocation)).all())


def record_fill(
    session: Session,
    *,
    mode: str,
    order: Order,
    qty: Decimal,
    price: Decimal,
    fee: Decimal,
) -> Fill:
    """Attribute a fill to the strategy sub-ledger and append the Trade row.

    Shared by every executor — the bookkeeping is identical whether the fill
    came from the simulator, Binance Testnet or live trading; only `mode`
    (recorded on the Trade) differs.
    """
    realized_before = get_or_create_position(
        session, order.strategy, order.market, order.symbol
    ).realized_pnl
    pos = apply_fill(
        session,
        strategy=order.strategy,
        market=order.market,
        symbol=order.symbol,
        side=order.side,
        qty=qty,
        price=price,
        fee=fee,
    )
    realized = pos.realized_pnl - realized_before
    trade = Trade(
        strategy=order.strategy,
        market=order.market,
        symbol=order.symbol,
        side=order.side.value,
        quantity=qty,
        price=price,
        fee=fee,
        realized_pnl=realized,
        mode=mode,
        executed_at=_utcnow(),
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return Fill(
        strategy=order.strategy,
        market=order.market,
        symbol=order.symbol,
        side=order.side,
        quantity=qty,
        price=price,
        fee=fee,
        realized_pnl=realized,
    )


def enforce_allocation(
    position: Position, allocation: Decimal, order: Order, price: Decimal
) -> Order | None:
    """Clip `order` so the strategy's exposure stays within its allocation.

    Allocation caps the *absolute* position value (`|qty| * price`). An order
    that only reduces exposure is always allowed in full; one that would push
    exposure past the budget is clipped to the remaining headroom. Returns the
    order unchanged, a quantity-reduced copy, or `None` when nothing fits.
    """
    price = Decimal(price)
    if price <= 0 or order.quantity <= 0:
        return None

    cap_qty = max(Decimal(allocation), Decimal(0)) / price  # max |position size|
    signed = _signed_qty(position)
    # Headroom on the order's side before the absolute cap is breached.
    headroom = cap_qty - signed if order.side is FillSide.buy else cap_qty + signed
    if headroom <= 0:
        return None
    if order.quantity <= headroom:
        return order
    return order.model_copy(update={"quantity": headroom})

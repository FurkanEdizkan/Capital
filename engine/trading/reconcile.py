"""Reconciliation — keep the engine's sub-ledger honest against the venue.

The venue holds one account-level position per symbol; the engine keeps a
per-strategy `Position` sub-ledger. They can drift — a venue-side close, a
partial fill, or a crash between placing an order and recording it. These
helpers compare the two so the operator (or a startup hook) can detect and
surface the mismatch rather than trading on stale state.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from trading.models import Position, PositionSide, Trade
from venues.base import Venue

# Quantities below this are treated as equal — guards against dust rounding.
DEFAULT_TOLERANCE = Decimal("0.00000001")


@dataclass
class PositionDiscrepancy:
    """A mismatch between the engine sub-ledger and the exchange."""

    market: str
    symbol: str
    engine_qty: Decimal  # net signed quantity summed across strategies
    exchange_qty: Decimal  # signed quantity reported by the venue

    @property
    def drift(self) -> Decimal:
        """Exchange minus engine — the unattributed quantity."""
        return self.exchange_qty - self.engine_qty


def engine_positions(session: Session) -> dict[tuple[str, str], Decimal]:
    """Net signed position per `(market, symbol)`, summed across strategies."""
    totals: dict[tuple[str, str], Decimal] = {}
    for pos in session.exec(select(Position)).all():
        if pos.side == PositionSide.long.value:
            signed = pos.qty
        elif pos.side == PositionSide.short.value:
            signed = -pos.qty
        else:
            continue  # flat — contributes nothing
        key = (pos.market, pos.symbol)
        totals[key] = totals.get(key, Decimal(0)) + signed
    return totals


def reconcile_positions(
    session: Session,
    exchange_positions: dict[tuple[str, str], Decimal],
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> list[PositionDiscrepancy]:
    """Compare the engine sub-ledger to exchange positions.

    Returns one `PositionDiscrepancy` per `(market, symbol)` whose engine and
    exchange quantities differ by more than `tolerance`.
    """
    engine = engine_positions(session)
    discrepancies: list[PositionDiscrepancy] = []
    for key in sorted(set(engine) | set(exchange_positions)):
        eng = engine.get(key, Decimal(0))
        exch = exchange_positions.get(key, Decimal(0))
        if abs(eng - exch) > tolerance:
            discrepancies.append(
                PositionDiscrepancy(
                    market=key[0], symbol=key[1], engine_qty=eng, exchange_qty=exch
                )
            )
    return discrepancies


def untracked_order_ids(
    session: Session, exchange_order_ids: list[str]
) -> list[str]:
    """Exchange `clientOrderId`s that have no recorded Trade row.

    A non-empty result means an order reached the venue but the engine crashed
    before recording it — the operator must attribute and record it by hand,
    since a bare clientOrderId does not name the strategy.
    """
    known = {
        t.client_order_id
        for t in session.exec(select(Trade)).all()
        if t.client_order_id
    }
    return [oid for oid in exchange_order_ids if oid not in known]


def reconcile_with_venue(
    session: Session, venue: Venue, *, market: str = "futures"
) -> list[PositionDiscrepancy]:
    """Fetch live positions from a `Venue` and reconcile them.

    `Venue.positions()` returns `{symbol: signed quantity}`; each is attributed
    to `market` so it keys the engine sub-ledger. Binance reports only futures
    positions (spot holdings are balances, not positions), so `market` defaults
    to "futures".
    """
    exchange = {
        (market, symbol): qty for symbol, qty in venue.positions().items()
    }
    return reconcile_positions(session, exchange)

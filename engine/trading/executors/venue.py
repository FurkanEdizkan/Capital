"""VenueExecutor — places real orders through the `Venue` interface.

The executor is venue-agnostic: it sizes an order against the instrument's
trading filters, submits it through `Venue.place_order`, and records the fill
in the shared sub-ledger. Whether the venue is Binance, Alpaca or Polymarket —
and whether it points at a testnet or a live account — is decided by the
`Venue` instance handed in, not by this class.

`SimExecutor` (sim.py) stays separate: it never touches a venue.
"""

import logging
from decimal import Decimal
from uuid import uuid4

from sqlmodel import Session

from trading.executors.base import (
    DEFAULT_FILTERS,
    BaseExecutor,
    ExecutionError,
    Fill,
    Order,
    SymbolFilters,
)
from trading.portfolio import record_fill
from venues.base import OrderRequest, Venue, VenueError

log = logging.getLogger("capital.trading.executors.venue")


class VenueExecutor(BaseExecutor):
    """Executes orders against a real account through a `Venue`."""

    def __init__(self, venue: Venue, *, mode: str) -> None:
        self._venue = venue
        self.mode = mode
        # Instrument filters are fetched once per (symbol, market) and cached.
        self._filters: dict[tuple[str, str | None], SymbolFilters] = {}

    def filters_for(self, symbol: str, market: str | None) -> SymbolFilters:
        """Trading filters for `symbol`, fetched from the venue and cached.

        Falls back to permissive defaults if the venue cannot describe the
        instrument — better to attempt the order than to never trade.
        """
        key = (symbol, market)
        cached = self._filters.get(key)
        if cached is not None:
            return cached
        try:
            inst = self._venue.instrument(symbol, market=market)
            filt = SymbolFilters(
                tick_size=inst.tick_size,
                step_size=inst.size_step,
                min_notional=inst.min_notional,
            )
        except VenueError:
            log.warning("no instrument filters for %s — using defaults", symbol)
            filt = DEFAULT_FILTERS
        self._filters[key] = filt
        return filt

    def execute(
        self, session: Session, order: Order, *, reference_price: Decimal
    ) -> Fill:
        """Submit `order` through the venue and record the resulting fill.

        `reference_price` is used only to pre-validate the order against the
        instrument's MIN_NOTIONAL — the venue sets the actual fill price.
        """
        filt = self.filters_for(order.symbol, order.market)
        qty = filt.round_quantity(order.quantity)
        if qty <= 0:
            raise ExecutionError(
                f"quantity {order.quantity} rounds to zero at step {filt.step_size}"
            )
        ref = Decimal(reference_price)
        if ref > 0 and qty * ref < filt.min_notional:
            raise ExecutionError(
                f"notional {qty * ref} below MIN_NOTIONAL {filt.min_notional}"
            )

        # A unique clientOrderId lets restart reconciliation match a placed
        # order back to its recorded trade.
        client_order_id = uuid4().hex
        try:
            result = self._venue.place_order(
                OrderRequest(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=qty,
                    market=order.market,
                    client_order_id=client_order_id,
                )
            )
        except VenueError as exc:
            raise ExecutionError(f"venue rejected order: {exc}") from exc

        if result.filled_quantity <= 0:
            raise ExecutionError("order returned no fill")

        return record_fill(
            session,
            mode=self.mode,
            order=order,
            qty=result.filled_quantity,
            price=result.price,
            fee=result.fee,
            client_order_id=result.client_order_id or client_order_id,
        )

"""LiveExecutor — places real orders on Binance (spot & USDⓈ-M futures).

The executor rounds an order to the symbol's trading filters, submits a
MARKET order through python-binance, parses the resulting fill, and records
it through the shared sub-ledger (`record_fill`). Futures orders first ensure
the symbol's leverage and margin mode are configured.

`TestnetExecutor` (testnet.py) is this class with a `testnet` mode label — the
testnet-vs-live difference is the injected `Client` (built with `testnet=True`),
not the executor logic.
"""

import logging
from decimal import Decimal
from typing import Any

from binance.exceptions import BinanceAPIException
from sqlmodel import Session

from trading.executors.base import (
    DEFAULT_FILTERS,
    BaseExecutor,
    ExecutionError,
    Fill,
    Order,
    SymbolFilters,
)
from trading.models import FillSide
from trading.portfolio import record_fill

log = logging.getLogger("capital.trading.executors.live")

# Fallback taker fee when the exchange response carries no commission
# (futures MARKET responses do not include it).
DEFAULT_FEE_RATE = Decimal("0.0004")


class LiveExecutor(BaseExecutor):
    """Executes orders against a real Binance account via python-binance."""

    mode = "live"

    def __init__(
        self,
        client: Any,
        *,
        fee_rate: Decimal = DEFAULT_FEE_RATE,
        filters: dict[str, SymbolFilters] | None = None,
        default_filters: SymbolFilters = DEFAULT_FILTERS,
        futures_leverage: int | None = None,
        futures_margin_type: str | None = None,
    ) -> None:
        self._client = client
        self.fee_rate = Decimal(fee_rate)
        self._filters = filters or {}
        self._default_filters = default_filters
        self.futures_leverage = futures_leverage
        self.futures_margin_type = futures_margin_type
        self._configured: set[str] = set()  # futures symbols already set up

    def filters_for(self, symbol: str) -> SymbolFilters:
        return self._filters.get(symbol, self._default_filters)

    # -- futures setup -------------------------------------------------------

    def _configure_futures(self, symbol: str) -> None:
        """Set leverage and margin mode for a futures symbol, once."""
        if symbol in self._configured:
            return
        if self.futures_leverage is not None:
            try:
                self._client.futures_change_leverage(
                    symbol=symbol, leverage=self.futures_leverage
                )
            except BinanceAPIException:
                log.warning("could not set leverage for %s", symbol)
        if self.futures_margin_type is not None:
            try:
                self._client.futures_change_margin_type(
                    symbol=symbol, marginType=self.futures_margin_type
                )
            except BinanceAPIException:
                # Binance rejects an unchanged margin type — that is fine.
                log.debug("margin type for %s already %s", symbol, self.futures_margin_type)
        self._configured.add(symbol)

    # -- order placement -----------------------------------------------------

    def _place(self, order: Order, qty: Decimal) -> dict[str, Any]:
        side = "BUY" if order.side is FillSide.buy else "SELL"
        if order.market == "futures":
            self._configure_futures(order.symbol)
            return self._client.futures_create_order(
                symbol=order.symbol, side=side, type="MARKET", quantity=str(qty)
            )
        return self._client.create_order(
            symbol=order.symbol, side=side, type="MARKET", quantity=str(qty)
        )

    def _parse(self, response: dict[str, Any], market: str) -> tuple[Decimal, Decimal, Decimal]:
        """Extract `(price, filled_qty, fee)` from a Binance order response."""
        if market == "futures":
            qty = Decimal(str(response.get("executedQty", "0")))
            price = Decimal(str(response.get("avgPrice", "0")))
            return price, qty, price * qty * self.fee_rate

        # Spot MARKET responses carry a per-trade `fills` breakdown.
        fills = response.get("fills") or []
        if fills:
            qty = sum((Decimal(str(f["qty"])) for f in fills), Decimal(0))
            quote = sum(
                (Decimal(str(f["price"])) * Decimal(str(f["qty"])) for f in fills),
                Decimal(0),
            )
            fee = sum((Decimal(str(f.get("commission", "0"))) for f in fills), Decimal(0))
            price = quote / qty if qty > 0 else Decimal(0)
            return price, qty, fee

        # Fallback — aggregate fields only.
        qty = Decimal(str(response.get("executedQty", "0")))
        quote = Decimal(str(response.get("cummulativeQuoteQty", "0")))
        price = quote / qty if qty > 0 else Decimal(0)
        return price, qty, price * qty * self.fee_rate

    # -- the executor interface ---------------------------------------------

    def execute(
        self, session: Session, order: Order, *, reference_price: Decimal
    ) -> Fill:
        """Submit `order` to Binance and record the resulting fill.

        `reference_price` is unused — the exchange determines the fill price —
        but kept for the shared executor interface.
        """
        del reference_price
        filt = self.filters_for(order.symbol)
        qty = filt.round_quantity(order.quantity)
        if qty <= 0:
            raise ExecutionError(
                f"quantity {order.quantity} rounds to zero at step {filt.step_size}"
            )

        try:
            response = self._place(order, qty)
        except BinanceAPIException as exc:
            raise ExecutionError(f"exchange rejected order: {exc}") from exc

        price, filled, fee = self._parse(response, order.market)
        if filled <= 0:
            raise ExecutionError("order returned no fill")

        return record_fill(
            session, mode=self.mode, order=order, qty=filled, price=price, fee=fee
        )

"""BinanceVenue — Binance behind the `Venue` interface.

The first concrete venue: it wraps the existing `BinanceClient` (market data,
instrument filters, account positions) and places MARKET orders through a
python-binance client. Binance becomes simply "the first venue" — see
docs/venue-abstraction.md.
"""

import logging
from decimal import Decimal
from typing import Any

from binance.exceptions import BinanceAPIException

from exchange.client import BinanceClient, Market
from trading.models import FillSide
from venues.base import (
    Instrument,
    OrderRequest,
    OrderResult,
    OrderType,
    Venue,
    VenueCandle,
    VenueError,
)

log = logging.getLogger("capital.venues.binance")

# Binance concatenates base+quote with no separator; match the common quotes.
_QUOTE_ASSETS = ("USDT", "USDC", "FDUSD", "BUSD", "TUSD", "USD", "BTC", "ETH", "BNB")


def _split_symbol(symbol: str) -> tuple[str, str]:
    """Split a Binance symbol into `(base, quote)` by a known quote suffix."""
    for quote in _QUOTE_ASSETS:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return symbol, ""


class BinanceVenue(Venue):
    """Binance spot or USDⓈ-M futures as a `Venue`."""

    name = "binance"
    supports_sandbox = True  # Binance offers a testnet

    def __init__(
        self,
        *,
        client: BinanceClient | None = None,
        order_client: Any | None = None,
        market: Market = Market.spot,
    ) -> None:
        # `client` serves market data; `order_client` (a python-binance
        # Client built with keys) places orders. A venue with no order
        # client is read-only.
        self._client = client or BinanceClient()
        self._order_client = order_client
        self._market = market

    def instrument(self, symbol: str) -> Instrument:
        try:
            filters = self._client.get_symbol_filters(symbol, self._market)
        except (ValueError, BinanceAPIException) as exc:
            raise VenueError(f"unknown Binance symbol {symbol!r}: {exc}") from exc
        base, quote = _split_symbol(symbol)
        return Instrument(
            symbol=symbol,
            base=base,
            quote=quote,
            tick_size=filters.tick_size,
            size_step=filters.step_size,
            min_notional=filters.min_notional,
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[VenueCandle]:
        klines = self._client.get_klines(symbol, interval, self._market, limit)
        return [
            VenueCandle(
                open_time=k.open_time,
                open=k.open,
                high=k.high,
                low=k.low,
                close=k.close,
                volume=k.volume,
            )
            for k in klines
        ]

    def price(self, symbol: str) -> Decimal:
        return self._client.get_ticker(symbol, self._market).price

    def place_order(self, request: OrderRequest) -> OrderResult:
        if self._order_client is None:
            raise VenueError("Binance venue is read-only — no order client configured")
        if request.order_type is not OrderType.market:
            raise VenueError("BinanceVenue currently places MARKET orders only")

        side = "BUY" if request.side is FillSide.buy else "SELL"
        place = (
            self._order_client.futures_create_order
            if self._market is Market.futures
            else self._order_client.create_order
        )
        try:
            response = place(
                symbol=request.symbol,
                side=side,
                type="MARKET",
                quantity=str(request.quantity),
            )
        except BinanceAPIException as exc:
            raise VenueError(f"Binance rejected the order: {exc}") from exc

        price, filled, fee = self._parse_fill(response)
        if filled <= 0:
            raise VenueError("Binance order returned no fill")
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=filled,
            price=price,
            fee=fee,
            order_id=str(response.get("orderId", "")),
        )

    def positions(self) -> dict[str, Decimal]:
        # Spot holdings are balances, not positions — only futures reconcile here.
        if self._market is Market.futures:
            return self._client.get_futures_positions()
        return {}

    def _parse_fill(self, response: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
        """Extract `(price, filled_qty, fee)` from a Binance order response."""
        fills = response.get("fills") or []
        if fills:
            qty = sum((Decimal(str(f["qty"])) for f in fills), Decimal(0))
            quote = sum(
                (Decimal(str(f["price"])) * Decimal(str(f["qty"])) for f in fills),
                Decimal(0),
            )
            fee = sum((Decimal(str(f.get("commission", "0"))) for f in fills), Decimal(0))
            return (quote / qty if qty > 0 else Decimal(0)), qty, fee
        # Futures responses report aggregates rather than per-trade fills.
        qty = Decimal(str(response.get("executedQty", "0")))
        price = Decimal(str(response.get("avgPrice", "0")))
        return price, qty, Decimal(0)

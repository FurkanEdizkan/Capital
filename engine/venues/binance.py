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

# Fallback taker fee when a Binance response carries no commission — futures
# MARKET responses report aggregates without a per-trade `fills` breakdown.
DEFAULT_FEE_RATE = Decimal("0.0004")


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
    fee_rate = Decimal("0.001")  # representative spot taker fee (0.1%)

    def __init__(
        self,
        *,
        client: BinanceClient | None = None,
        order_client: Any | None = None,
        market: Market = Market.spot,
        fee_rate: Decimal = DEFAULT_FEE_RATE,
        futures_leverage: int | None = None,
        futures_margin_type: str | None = None,
    ) -> None:
        # `client` serves market data; `order_client` (a python-binance
        # Client built with keys) places orders. A venue with no order
        # client is read-only.
        self._client_cache = client  # built lazily on first use if None
        self._order_client = order_client
        self._market = market
        self._fee_rate = Decimal(fee_rate)
        self._futures_leverage = futures_leverage
        self._futures_margin_type = futures_margin_type
        self._configured: set[str] = set()  # futures symbols already set up

    @property
    def _client(self) -> BinanceClient:
        # Lazy — constructing a python-binance client touches the network,
        # so a venue is cheap to build (and unit-testable) until first used.
        if self._client_cache is None:
            self._client_cache = BinanceClient()
        return self._client_cache

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        m = Market(market) if market is not None else self._market
        try:
            filters = self._client.get_symbol_filters(symbol, m)
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
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        # `market` overrides the venue's default market for this fetch — so a
        # single Binance venue serves both spot and futures candle requests.
        klines_market = Market(market) if market is not None else self._market
        klines = self._client.get_klines(symbol, interval, klines_market, limit)
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

    def _configure_futures(self, symbol: str) -> None:
        """Set leverage and margin mode for a futures symbol, once per symbol."""
        if symbol in self._configured:
            return
        if self._futures_leverage is not None:
            try:
                self._order_client.futures_change_leverage(
                    symbol=symbol, leverage=self._futures_leverage
                )
            except BinanceAPIException:
                log.warning("could not set leverage for %s", symbol)
        if self._futures_margin_type is not None:
            try:
                self._order_client.futures_change_margin_type(
                    symbol=symbol, marginType=self._futures_margin_type
                )
            except BinanceAPIException:
                # Binance rejects an unchanged margin type — that is fine.
                log.debug("margin type for %s already set", symbol)
        self._configured.add(symbol)

    def place_order(self, request: OrderRequest) -> OrderResult:
        if self._order_client is None:
            raise VenueError("Binance venue is read-only — no order client configured")
        if request.order_type is not OrderType.market:
            raise VenueError("BinanceVenue currently places MARKET orders only")

        m = Market(request.market) if request.market is not None else self._market
        side = "BUY" if request.side is FillSide.buy else "SELL"
        params: dict[str, Any] = {
            "symbol": request.symbol,
            "side": side,
            "type": "MARKET",
            "quantity": str(request.quantity),
        }
        # A deterministic clientOrderId makes placement idempotent — restart
        # reconciliation can match a placed order back to its recorded trade.
        if request.client_order_id is not None:
            params["newClientOrderId"] = request.client_order_id

        if m is Market.futures:
            self._configure_futures(request.symbol)
            place = self._order_client.futures_create_order
        else:
            place = self._order_client.create_order
        try:
            response = place(**params)
        except BinanceAPIException as exc:
            raise VenueError(f"Binance rejected the order: {exc}") from exc

        price, filled, fee = self._parse_fill(response, m)
        if filled <= 0:
            raise VenueError("Binance order returned no fill")
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=filled,
            price=price,
            fee=fee,
            order_id=str(response.get("orderId", "")),
            client_order_id=request.client_order_id or "",
        )

    def positions(self) -> dict[str, Decimal]:
        # Spot holdings are balances, not positions — only futures reconcile here.
        if self._market is Market.futures:
            return self._client.get_futures_positions()
        return {}

    def _parse_fill(
        self, response: dict[str, Any], market: Market
    ) -> tuple[Decimal, Decimal, Decimal]:
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
        # Futures responses report aggregates rather than per-trade fills, and
        # carry no commission — estimate it from the venue's taker fee rate.
        qty = Decimal(str(response.get("executedQty", "0")))
        price = Decimal(str(response.get("avgPrice", "0")))
        return price, qty, price * qty * self._fee_rate

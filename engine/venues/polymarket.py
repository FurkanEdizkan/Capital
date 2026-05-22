"""PolymarketVenue — prediction markets behind the `Venue` interface.

Polymarket's CLOB exposes a public market-data API (midpoint, price history)
and an authenticated order API. Reading data is open; placing an order needs
a wallet-signed payload, so order placement is delegated to an injected
signing client. There is no sandbox — see docs/venue-research.md.

A `symbol` here is a Polymarket outcome **token id** (an ERC-1155 token).
Prices are probabilities in the range 0..1; collateral is USDC.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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

log = logging.getLogger("capital.venues.polymarket")

_CLOB_API = "https://clob.polymarket.com"
_DATA_API = "https://data-api.polymarket.com"

# Capital intervals → Polymarket price-history intervals.
_INTERVALS = {"1m": "1m", "1h": "1h", "1d": "1d", "1w": "1w"}


class PolymarketVenue(Venue):
    """Polymarket prediction markets via the CLOB API."""

    name = "polymarket"
    supports_sandbox = False  # Polymarket has no paper environment
    fee_rate = Decimal("0")  # Polymarket CLOB charges no trading fee

    def __init__(
        self,
        *,
        http: Any | None = None,
        order_client: Any | None = None,
        wallet_address: str = "",
    ) -> None:
        # `http` serves public market data; `order_client` signs and submits
        # orders (it wraps the wallet); `wallet_address` enables position reads.
        self._http = http if http is not None else self._build_client()
        self._order_client = order_client
        self._wallet_address = wallet_address

    @staticmethod
    def _build_client() -> Any:
        import httpx

        return httpx.Client(timeout=30.0)

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = self._http.get(url, params=params)
        if response.status_code >= 400:
            raise VenueError(
                f"Polymarket request failed ({response.status_code}): {url}"
            )
        return response.json()

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        del market  # single market — accepted for interface parity, ignored
        # Every Polymarket outcome token is uniform: 1-cent ticks, USDC
        # collateral, prices in 0..1.
        return Instrument(
            symbol=symbol,
            base=symbol,
            quote="USDC",
            tick_size=Decimal("0.01"),
            size_step=Decimal("0.01"),
            min_notional=Decimal("1"),
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        del market  # single market — accepted for interface parity, ignored
        poly_interval = _INTERVALS.get(interval)
        if poly_interval is None:
            raise VenueError(f"Polymarket: unsupported interval {interval!r}")
        payload = self._get(
            f"{_CLOB_API}/prices-history",
            params={"market": symbol, "interval": poly_interval},
        )
        history = payload.get("history", [])[-limit:]
        # A prediction market has a price series, not OHLCV — each point
        # becomes a degenerate candle (open = high = low = close).
        return [
            VenueCandle(
                open_time=datetime.fromtimestamp(int(point["t"]), tz=UTC),
                open=Decimal(str(point["p"])),
                high=Decimal(str(point["p"])),
                low=Decimal(str(point["p"])),
                close=Decimal(str(point["p"])),
                volume=Decimal("0"),
            )
            for point in history
        ]

    def price(self, symbol: str) -> Decimal:
        payload = self._get(f"{_CLOB_API}/midpoint", params={"token_id": symbol})
        return Decimal(str(payload["mid"]))

    def place_order(self, request: OrderRequest) -> OrderResult:
        if self._order_client is None:
            raise VenueError("Polymarket venue is read-only — no signing client")
        if request.order_type is not OrderType.market:
            raise VenueError("PolymarketVenue currently places MARKET orders only")

        side = "BUY" if request.side is FillSide.buy else "SELL"
        try:
            result = self._order_client.place_market_order(
                token_id=request.symbol, side=side, size=request.quantity
            )
        except Exception as exc:  # noqa: BLE001 — normalise signing-client errors
            raise VenueError(f"Polymarket order failed: {exc}") from exc

        filled = Decimal(str(result.get("size", "0")))
        if filled <= 0:
            raise VenueError("Polymarket order did not fill")
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=filled,
            price=Decimal(str(result.get("price", "0"))),
            fee=Decimal(str(result.get("fee", "0"))),
            order_id=str(result.get("orderID", "")),
        )

    def positions(self) -> dict[str, Decimal]:
        # Polymarket positions settle on-chain; the data API reports them per
        # wallet. Without a wallet address there is nothing to reconcile.
        if not self._wallet_address:
            return {}
        rows = self._get(
            f"{_DATA_API}/positions", params={"user": self._wallet_address}
        )
        return {
            row["asset"]: Decimal(str(row["size"]))
            for row in rows
            if Decimal(str(row.get("size", "0"))) != 0
        }

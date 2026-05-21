"""AlpacaVenue — US stock trading behind the `Venue` interface.

Alpaca's REST API is small enough to call directly over `httpx` (no extra
SDK). The venue covers the trading API (orders, positions, assets) and the
market-data API (bars, latest trade). It is the recommended first stock
venue — see docs/venue-research.md.
"""

import logging
from datetime import datetime
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

log = logging.getLogger("capital.venues.alpaca")

_LIVE_API = "https://api.alpaca.markets"
_PAPER_API = "https://paper-api.alpaca.markets"
_DATA_API = "https://data.alpaca.markets"

# Capital's Binance-style intervals → Alpaca bar timeframes.
_TIMEFRAMES = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "1d": "1Day",
}


class AlpacaVenue(Venue):
    """US equities via Alpaca (paper or live)."""

    name = "alpaca"
    supports_sandbox = True  # Alpaca's paper environment

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        paper: bool = True,
        http: Any | None = None,
    ) -> None:
        self._trading = _PAPER_API if paper else _LIVE_API
        self._data = _DATA_API
        # `http` is an httpx.Client-like object; injected in tests.
        self._http = http if http is not None else self._build_client(api_key, api_secret)

    @staticmethod
    def _build_client(api_key: str, api_secret: str) -> Any:
        import httpx

        return httpx.Client(
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
            timeout=30.0,
        )

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = self._http.get(url, params=params)
        if response.status_code == 404:
            raise VenueError(f"Alpaca: not found — {url}")
        if response.status_code >= 400:
            raise VenueError(f"Alpaca request failed ({response.status_code}): {url}")
        return response.json()

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        del market  # single market — accepted for interface parity, ignored
        asset = self._get(f"{self._trading}/v2/assets/{symbol}")
        if not asset.get("tradable", False):
            raise VenueError(f"Alpaca asset {symbol!r} is not tradable")
        # US equities trade in $0.01 increments and whole shares.
        return Instrument(
            symbol=symbol,
            base=symbol,
            quote="USD",
            tick_size=Decimal("0.01"),
            size_step=Decimal("1"),
            min_notional=Decimal("1"),
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        del market  # single market — accepted for interface parity, ignored
        timeframe = _TIMEFRAMES.get(interval)
        if timeframe is None:
            raise VenueError(f"Alpaca: unsupported interval {interval!r}")
        payload = self._get(
            f"{self._data}/v2/stocks/{symbol}/bars",
            params={"timeframe": timeframe, "limit": limit},
        )
        return [
            VenueCandle(
                open_time=datetime.fromisoformat(bar["t"]),
                open=Decimal(str(bar["o"])),
                high=Decimal(str(bar["h"])),
                low=Decimal(str(bar["l"])),
                close=Decimal(str(bar["c"])),
                volume=Decimal(str(bar["v"])),
            )
            for bar in payload.get("bars", [])
        ]

    def price(self, symbol: str) -> Decimal:
        payload = self._get(f"{self._data}/v2/stocks/{symbol}/trades/latest")
        return Decimal(str(payload["trade"]["p"]))

    def place_order(self, request: OrderRequest) -> OrderResult:
        if request.order_type is not OrderType.market:
            raise VenueError("AlpacaVenue currently places MARKET orders only")
        side = "buy" if request.side is FillSide.buy else "sell"
        response = self._http.post(
            f"{self._trading}/v2/orders",
            json={
                "symbol": request.symbol,
                "qty": str(request.quantity),
                "side": side,
                "type": "market",
                "time_in_force": "day",
            },
        )
        if response.status_code >= 400:
            raise VenueError(f"Alpaca rejected the order ({response.status_code})")
        order = response.json()

        # A market order fills near-instantly — read it back once for the fill.
        order = self._get(f"{self._trading}/v2/orders/{order['id']}")
        filled = Decimal(str(order.get("filled_qty") or "0"))
        if filled <= 0:
            raise VenueError("Alpaca order has not filled")
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=filled,
            price=Decimal(str(order.get("filled_avg_price") or "0")),
            fee=Decimal("0"),  # Alpaca equities are commission-free
            order_id=str(order["id"]),
        )

    def positions(self) -> dict[str, Decimal]:
        rows = self._get(f"{self._trading}/v2/positions")
        positions: dict[str, Decimal] = {}
        for row in rows:
            qty = Decimal(str(row["qty"]))
            if row.get("side") == "short":
                qty = -abs(qty)
            positions[row["symbol"]] = qty
        return positions

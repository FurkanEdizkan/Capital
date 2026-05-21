"""BinanceAlphaVenue — Binance Alpha tokenized stocks behind the `Venue` interface.

Binance Alpha is a separate trading surface from the Binance spot/futures API
(see docs/venue-research.md, issue #118 spike). It hosts the Ondo Finance
tokenized US equities — AAPLon, TSLAon, NVDAon, QQQon and the like.

Its **public market-data** endpoints are documented and need no credentials.
A documented public **order-placement** API was not confirmed, so this venue
is **read-only**: `place_order` raises `VenueError`. Tokenized stocks are
therefore tradeable in Sim mode (the simulator fills on live Alpha prices)
but not yet on Testnet/Live.

A `symbol` here is an Alpha pair id, formatted `ALPHA_<token_id><quote>` —
e.g. `ALPHA_175USDT`. The `get-exchange-info` endpoint lists the live pairs.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from venues.base import (
    Instrument,
    OrderRequest,
    OrderResult,
    Venue,
    VenueCandle,
    VenueError,
)

log = logging.getLogger("capital.venues.binance_alpha")

_ALPHA_API = "https://www.binance.com/bapi/defi/v1/public/alpha-trade"

# Default trading filters when a pair is not found in exchange-info — Alpha
# is read-only here, so these only feed the venue-neutral sizing logic.
_DEFAULT_TICK = Decimal("0.0001")
_DEFAULT_STEP = Decimal("0.0001")
_DEFAULT_MIN_NOTIONAL = Decimal("1")


class BinanceAlphaVenue(Venue):
    """Binance Alpha tokenized stocks — read-only market data."""

    name = "binance-alpha"
    supports_sandbox = False  # Binance Alpha has no paper environment

    def __init__(self, *, http: Any | None = None) -> None:
        # `http` is an httpx.Client-like object; injected in tests.
        self._http = http if http is not None else self._build_client()

    @staticmethod
    def _build_client() -> Any:
        import httpx

        return httpx.Client(timeout=30.0)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET an Alpha endpoint and unwrap the `{code, success, data}` envelope."""
        response = self._http.get(f"{_ALPHA_API}/{path}", params=params)
        if response.status_code >= 400:
            raise VenueError(
                f"Binance Alpha request failed ({response.status_code}): {path}"
            )
        payload = response.json()
        if not payload.get("success", False):
            raise VenueError(
                f"Binance Alpha error: {payload.get('message') or payload.get('code')}"
            )
        return payload.get("data")

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        del market  # Alpha is a single market
        rows = self._get("get-exchange-info") or []
        row = next((r for r in rows if r.get("symbol") == symbol), None)
        if row is None:
            raise VenueError(f"unknown Binance Alpha symbol {symbol!r}")
        filters = {f.get("filterType"): f for f in row.get("filters", [])}
        tick = filters.get("PRICE_FILTER", {}).get("tickSize")
        step = filters.get("LOT_SIZE", {}).get("stepSize")
        notional = filters.get("MIN_NOTIONAL", {}).get("minNotional")
        return Instrument(
            symbol=symbol,
            base=row.get("baseAsset", symbol),
            quote=row.get("quoteAsset", "USDT"),
            tick_size=Decimal(str(tick)) if tick else _DEFAULT_TICK,
            size_step=Decimal(str(step)) if step else _DEFAULT_STEP,
            min_notional=(
                Decimal(str(notional)) if notional else _DEFAULT_MIN_NOTIONAL
            ),
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        del market  # Alpha is a single market
        rows = self._get(
            "klines", params={"symbol": symbol, "interval": interval, "limit": limit}
        )
        # Each kline is a 12-element array: [openTime, o, h, l, c, volume, ...].
        return [
            VenueCandle(
                open_time=datetime.fromtimestamp(int(k[0]) / 1000, tz=UTC),
                open=Decimal(str(k[1])),
                high=Decimal(str(k[2])),
                low=Decimal(str(k[3])),
                close=Decimal(str(k[4])),
                volume=Decimal(str(k[5])),
            )
            for k in (rows or [])
        ]

    def price(self, symbol: str) -> Decimal:
        ticker = self._get("ticker", params={"symbol": symbol})
        return Decimal(str(ticker["lastPrice"]))

    def place_order(self, request: OrderRequest) -> OrderResult:
        # Binance Alpha has no confirmed public order API — this venue is
        # read-only. Tokenized stocks are tradeable in Sim mode only.
        raise VenueError(
            "Binance Alpha venue is read-only — order placement is not yet wired"
        )

    def positions(self) -> dict[str, Decimal]:
        # No account/position endpoint is wired — nothing to reconcile.
        return {}

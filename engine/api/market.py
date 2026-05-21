"""Market-data API — REST endpoints + a live ticker WebSocket.

Wires together the Binance REST client (issue #9), the candle cache
(issue #11) and the WebSocket streams (issue #10). All endpoints require an
authenticated operator.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from auth.deps import CurrentUser, SessionDep
from auth.security import decode_token
from exchange.client import (
    BinanceClient,
    FundingRate,
    Market,
    OrderBook,
    Ticker,
)
from marketdata.cache import refresh_venue_candles
from marketdata.models import Candle
from marketdata.stream import StreamManager
from trading.venue_router import VenueRouter

log = logging.getLogger("capital.api.market")

router = APIRouter(prefix="/api/market", tags=["market"])
ws_router = APIRouter()

_client: BinanceClient | None = None


def get_binance_client() -> BinanceClient:
    """Lazily-constructed shared REST client (overridable in tests)."""
    global _client
    if _client is None:
        _client = BinanceClient()
    return _client


def get_stream_manager(request: Request) -> StreamManager:
    """The live-stream manager created in the app lifespan."""
    return request.app.state.streams


_venue_router: VenueRouter | None = None


def get_venue_router() -> VenueRouter:
    """Lazily-constructed shared venue router (overridable in tests)."""
    global _venue_router
    if _venue_router is None:
        _venue_router = VenueRouter.default()
    return _venue_router


ClientDep = Annotated[BinanceClient, Depends(get_binance_client)]
StreamsDep = Annotated[StreamManager, Depends(get_stream_manager)]
VenueRouterDep = Annotated[VenueRouter, Depends(get_venue_router)]


@router.get("/tickers", response_model=list[Ticker])
def list_tickers(
    _: CurrentUser,
    streams: StreamsDep,
    client: ClientDep,
    market: Market = Market.spot,
) -> list[Ticker]:
    """Latest 24h tickers — from the live snapshot, or REST as a fallback."""
    snapshot = streams.hub(market).snapshot()
    return snapshot if snapshot else client.get_tickers(market)


@router.get("/klines", response_model=list[Candle])
def get_klines(
    _: CurrentUser,
    venues: VenueRouterDep,
    session: SessionDep,
    symbol: str = Query(min_length=3, max_length=24),
    interval: str = "1h",
    market: Market = Market.spot,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[Candle]:
    """Candle history — served from the cache, refreshed from the active venue."""
    return refresh_venue_candles(
        session,
        venues.resolve(session),
        market=market,
        symbol=symbol,
        interval=interval,
        limit=limit,
    )


@router.get("/funding", response_model=FundingRate)
def get_funding(_: CurrentUser, client: ClientDep, symbol: str) -> FundingRate:
    """Current futures funding rate for a symbol."""
    return client.get_funding(symbol)


@router.get("/orderbook", response_model=OrderBook)
def get_orderbook(
    _: CurrentUser,
    client: ClientDep,
    symbol: str,
    market: Market = Market.spot,
    limit: int = Query(default=20, ge=5, le=100),
) -> OrderBook:
    """Order-book depth for a symbol."""
    return client.get_order_book(symbol, market, limit)


@ws_router.websocket("/ws/market")
async def market_stream(websocket: WebSocket, token: str = Query(...)) -> None:
    """Push live ticker snapshots to the UI (~1/s).

    The browser WebSocket API can't send an Authorization header, so the
    access token is passed as a query parameter and validated here.
    """
    try:
        decode_token(token, "access")
    except jwt.InvalidTokenError:
        await websocket.close(code=1008)  # policy violation
        return

    await websocket.accept()
    streams: StreamManager = websocket.app.state.streams
    try:
        while True:
            payload = {
                "spot": [t.model_dump(mode="json") for t in streams.spot.snapshot()],
                "futures": [t.model_dump(mode="json") for t in streams.futures.snapshot()],
            }
            await websocket.send_json(
                {
                    "type": "tickers",
                    "ts": datetime.now(UTC).isoformat(),
                    "payload": payload,
                }
            )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass

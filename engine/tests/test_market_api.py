"""Tests for the market-data API — REST endpoints + the ticker WebSocket."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from starlette.websockets import WebSocketDisconnect

from api.market import get_binance_client, get_stream_manager, get_venue_router
from db import get_session
from exchange.client import FundingRate, Kline, Market, OrderBook, OrderBookLevel, Ticker
from main import app
from tests.conftest import ADMIN_PASSWORD, login
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


def _ticker(sym: str, price: str) -> Ticker:
    return Ticker(
        symbol=sym,
        price=Decimal(price),
        change_pct_24h=Decimal("1.5"),
        quote_volume_24h=Decimal("1000000"),
    )


class FakeHub:
    def __init__(self, tickers: list[Ticker]) -> None:
        self._t = tickers

    def snapshot(self) -> list[Ticker]:
        return self._t


class FakeStreams:
    def __init__(self) -> None:
        self.spot = FakeHub([_ticker("BTCUSDT", "68000"), _ticker("ETHUSDT", "3400")])
        self.futures = FakeHub([])  # empty → REST fallback exercised

    def hub(self, market: Market) -> FakeHub:
        return self.futures if market is Market.futures else self.spot


class FakeBinance:
    def get_tickers(self, market: Market) -> list[Ticker]:
        return [_ticker("SOLUSDT", "170")]

    def get_klines(self, *_: Any, **__: Any) -> list[Kline]:
        base = datetime(2024, 5, 20, tzinfo=UTC)
        return [
            Kline(
                open_time=base,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=Decimal("1000"),
                close_time=base,
            )
        ]

    def get_funding(self, symbol: str) -> FundingRate:
        return FundingRate(
            symbol=symbol,
            funding_rate=Decimal("0.0001"),
            mark_price=Decimal("68000"),
            next_funding_time=datetime(2024, 5, 20, tzinfo=UTC),
        )

    def get_order_book(self, symbol: str, *_: Any, **__: Any) -> OrderBook:
        return OrderBook(
            symbol=symbol,
            bids=[OrderBookLevel(price=Decimal("1"), qty=Decimal("2"))],
            asks=[OrderBookLevel(price=Decimal("3"), qty=Decimal("4"))],
        )


class FakeVenue(Venue):
    """A venue whose `candles` records the market it was asked for."""

    name = "binance"

    def __init__(self) -> None:
        self.last_market: str | None = None

    def instrument(self, symbol: str) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        self.last_market = market
        base = datetime(2024, 5, 20, tzinfo=UTC)
        return [
            VenueCandle(
                open_time=base,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=Decimal("1000"),
            )
        ]

    def price(self, symbol: str) -> Decimal:
        return Decimal("105")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


@pytest.fixture
def market_client(session: Session) -> Iterator[TestClient]:
    fake_streams = FakeStreams()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_binance_client] = lambda: FakeBinance()
    app.dependency_overrides[get_venue_router] = lambda: VenueRouter(
        {"binance": FakeVenue()}
    )
    app.dependency_overrides[get_stream_manager] = lambda: fake_streams
    app.state.streams = fake_streams  # the WS endpoint reads app.state directly
    yield TestClient(app)
    app.dependency_overrides.clear()
    if hasattr(app.state, "streams"):
        delattr(app.state, "streams")


def test_tickers_requires_auth(market_client: TestClient) -> None:
    assert market_client.get("/api/market/tickers").status_code == 401


def test_tickers_returns_live_snapshot(market_client: TestClient) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    resp = market_client.get(
        "/api/market/tickers", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert {t["symbol"] for t in resp.json()} == {"BTCUSDT", "ETHUSDT"}


def test_tickers_falls_back_to_rest(market_client: TestClient) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    # futures hub is empty → endpoint falls back to the REST client
    resp = market_client.get(
        "/api/market/tickers?market=futures",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["symbol"] == "SOLUSDT"


def test_klines(market_client: TestClient) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    resp = market_client.get(
        "/api/market/klines?symbol=BTCUSDT&interval=1h",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_klines_futures_routes_market_through_the_venue(
    market_client: TestClient,
) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    resp = market_client.get(
        "/api/market/klines?symbol=BTCUSDT&interval=1h&market=futures",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    # The cached candle is stored under the requested market.
    assert resp.json()[0]["market"] == "futures"


def test_funding_and_orderbook(market_client: TestClient) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    h = {"Authorization": f"Bearer {token}"}
    assert market_client.get("/api/market/funding?symbol=BTCUSDT", headers=h).status_code == 200
    ob = market_client.get("/api/market/orderbook?symbol=BTCUSDT", headers=h)
    assert ob.status_code == 200
    assert Decimal(ob.json()["bids"][0]["price"]) == Decimal("1")


def test_ws_rejects_bad_token(market_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):  # noqa: PT012
        with market_client.websocket_connect("/ws/market?token=garbage") as ws:
            ws.receive_json()


def test_ws_streams_tickers(market_client: TestClient) -> None:
    token = login(market_client, "admin", ADMIN_PASSWORD)
    with market_client.websocket_connect(f"/ws/market?token={token}") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "tickers"
    assert {t["symbol"] for t in msg["payload"]["spot"]} == {"BTCUSDT", "ETHUSDT"}

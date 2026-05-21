"""Tests for AlpacaVenue — hermetic, fake HTTP client."""

from decimal import Decimal
from typing import Any

import pytest

from trading.models import FillSide
from venues.alpaca import AlpacaVenue
from venues.base import OrderRequest, OrderType, VenueError


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeHttp:
    """Routes Alpaca requests to canned responses by URL."""

    def __init__(self) -> None:
        self.posted: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        if "/v2/assets/" in url:
            if url.endswith("/NOPE"):
                return FakeResponse(404, {})
            if url.endswith("/HALTED"):
                return FakeResponse(200, {"symbol": "HALTED", "tradable": False})
            return FakeResponse(200, {"symbol": url.rsplit("/", 1)[-1], "tradable": True})
        if "/bars" in url:
            return FakeResponse(
                200,
                {
                    "bars": [
                        {
                            "t": "2026-01-02T14:30:00Z",
                            "o": 100,
                            "h": 105,
                            "l": 99,
                            "c": 102,
                            "v": 1000,
                        }
                    ]
                },
            )
        if "/trades/latest" in url:
            return FakeResponse(200, {"trade": {"p": 101.5}})
        if "/v2/orders/" in url:
            return FakeResponse(
                200, {"id": "ord-1", "filled_qty": "3", "filled_avg_price": "100.25"}
            )
        if url.endswith("/v2/positions"):
            return FakeResponse(
                200,
                [
                    {"symbol": "AAPL", "qty": "10", "side": "long"},
                    {"symbol": "TSLA", "qty": "4", "side": "short"},
                ],
            )
        return FakeResponse(404, {})

    def post(self, url: str, json: dict[str, Any] | None = None) -> FakeResponse:
        self.posted.append(json or {})
        return FakeResponse(200, {"id": "ord-1", "status": "accepted"})


def _venue() -> tuple[AlpacaVenue, FakeHttp]:
    http = FakeHttp()
    return AlpacaVenue(http=http), http


def test_instrument() -> None:
    venue, _ = _venue()
    inst = venue.instrument("AAPL")
    assert inst.symbol == "AAPL"
    assert inst.quote == "USD"
    assert inst.tick_size == Decimal("0.01")


def test_instrument_untradable_raises() -> None:
    venue, _ = _venue()
    with pytest.raises(VenueError):
        venue.instrument("HALTED")


def test_instrument_unknown_raises() -> None:
    venue, _ = _venue()
    with pytest.raises(VenueError):
        venue.instrument("NOPE")


def test_candles() -> None:
    venue, _ = _venue()
    candles = venue.candles("AAPL", "1h")
    assert len(candles) == 1
    assert candles[0].close == Decimal("102")
    assert candles[0].open_time.year == 2026


def test_candles_bad_interval_raises() -> None:
    venue, _ = _venue()
    with pytest.raises(VenueError):
        venue.candles("AAPL", "3h")


def test_price() -> None:
    venue, _ = _venue()
    assert venue.price("AAPL") == Decimal("101.5")


def test_place_order() -> None:
    venue, http = _venue()
    result = venue.place_order(
        OrderRequest(symbol="AAPL", side=FillSide.buy, quantity=Decimal("3"))
    )
    assert result.filled_quantity == Decimal("3")
    assert result.price == Decimal("100.25")
    assert result.fee == Decimal("0")  # commission-free
    assert result.order_id == "ord-1"
    assert http.posted[0]["symbol"] == "AAPL"
    assert http.posted[0]["side"] == "buy"


def test_limit_order_rejected() -> None:
    venue, _ = _venue()
    with pytest.raises(VenueError):
        venue.place_order(
            OrderRequest(
                symbol="AAPL",
                side=FillSide.buy,
                quantity=Decimal("1"),
                order_type=OrderType.limit,
                limit_price=Decimal("99"),
            )
        )


def test_positions_signs_shorts() -> None:
    venue, _ = _venue()
    assert venue.positions() == {"AAPL": Decimal("10"), "TSLA": Decimal("-4")}

"""Tests for PolymarketVenue — hermetic, fake HTTP and signing clients."""

from decimal import Decimal
from typing import Any

import pytest

from trading.models import FillSide
from venues.base import OrderRequest, OrderType, VenueError
from venues.polymarket import PolymarketVenue

_TOKEN = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeHttp:
    def get(self, url: str, params: dict[str, Any] | None = None) -> FakeResponse:
        if "/prices-history" in url:
            return FakeResponse(
                200,
                {"history": [{"t": 1767225600, "p": "0.61"}, {"t": 1767229200, "p": "0.63"}]},
            )
        if "/midpoint" in url:
            return FakeResponse(200, {"mid": "0.62"})
        if "/positions" in url:
            return FakeResponse(
                200,
                [
                    {"asset": _TOKEN, "size": "120"},
                    {"asset": "other", "size": "0"},
                ],
            )
        return FakeResponse(404, {})


class FakeOrderClient:
    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def place_market_order(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.raises:
            raise RuntimeError("signing failed")
        return {"orderID": "0xabc", "size": "50", "price": "0.62", "fee": "0"}


def test_instrument_is_a_uniform_outcome_token() -> None:
    inst = PolymarketVenue(http=FakeHttp()).instrument(_TOKEN)
    assert inst.quote == "USDC"
    assert inst.tick_size == Decimal("0.01")


def test_candles_from_price_history() -> None:
    candles = PolymarketVenue(http=FakeHttp()).candles(_TOKEN, "1h")
    assert len(candles) == 2
    # A prediction-market point is a degenerate candle: o = h = l = c.
    assert candles[0].open == candles[0].high == candles[0].close == Decimal("0.61")
    assert candles[1].close == Decimal("0.63")


def test_candles_bad_interval_raises() -> None:
    with pytest.raises(VenueError):
        PolymarketVenue(http=FakeHttp()).candles(_TOKEN, "4h")


def test_price_is_the_midpoint() -> None:
    assert PolymarketVenue(http=FakeHttp()).price(_TOKEN) == Decimal("0.62")


def test_place_order_delegates_to_the_signing_client() -> None:
    order_client = FakeOrderClient()
    venue = PolymarketVenue(http=FakeHttp(), order_client=order_client)
    result = venue.place_order(
        OrderRequest(symbol=_TOKEN, side=FillSide.buy, quantity=Decimal("50"))
    )
    assert result.filled_quantity == Decimal("50")
    assert result.price == Decimal("0.62")
    assert result.order_id == "0xabc"
    assert order_client.calls[0]["side"] == "BUY"


def test_read_only_venue_rejects_orders() -> None:
    with pytest.raises(VenueError):
        PolymarketVenue(http=FakeHttp()).place_order(
            OrderRequest(symbol=_TOKEN, side=FillSide.buy, quantity=Decimal("50"))
        )


def test_limit_order_rejected() -> None:
    venue = PolymarketVenue(http=FakeHttp(), order_client=FakeOrderClient())
    with pytest.raises(VenueError):
        venue.place_order(
            OrderRequest(
                symbol=_TOKEN,
                side=FillSide.buy,
                quantity=Decimal("50"),
                order_type=OrderType.limit,
                limit_price=Decimal("0.6"),
            )
        )


def test_signing_failure_raises_venue_error() -> None:
    venue = PolymarketVenue(http=FakeHttp(), order_client=FakeOrderClient(raises=True))
    with pytest.raises(VenueError):
        venue.place_order(
            OrderRequest(symbol=_TOKEN, side=FillSide.buy, quantity=Decimal("50"))
        )


def test_positions_without_a_wallet_is_empty() -> None:
    assert PolymarketVenue(http=FakeHttp()).positions() == {}


def test_positions_with_a_wallet_reads_the_data_api() -> None:
    venue = PolymarketVenue(http=FakeHttp(), wallet_address="0xWALLET")
    assert venue.positions() == {_TOKEN: Decimal("120")}  # zero-size row dropped

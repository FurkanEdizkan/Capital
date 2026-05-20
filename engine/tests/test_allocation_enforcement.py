"""Tests for `enforce_allocation` — capital-budget capping of orders."""

from decimal import Decimal

from trading.executors.base import Order
from trading.models import FillSide, Position, PositionSide
from trading.portfolio import enforce_allocation


def _flat() -> Position:
    return Position(strategy="S", market="spot", symbol="BTCUSDT")


def _long(qty: str) -> Position:
    return Position(
        strategy="S",
        market="spot",
        symbol="BTCUSDT",
        side=PositionSide.long.value,
        qty=Decimal(qty),
        entry_price=Decimal("100"),
    )


def _order(side: FillSide, qty: str) -> Order:
    return Order(strategy="S", market="spot", symbol="BTCUSDT", side=side, quantity=Decimal(qty))


def test_buy_within_allocation_passes_unchanged() -> None:
    order = _order(FillSide.buy, "10")  # 10 * 100 = 1000 = allocation
    result = enforce_allocation(_flat(), Decimal("1000"), order, Decimal("100"))
    assert result is order


def test_buy_exceeding_allocation_is_clipped() -> None:
    order = _order(FillSide.buy, "50")
    result = enforce_allocation(_flat(), Decimal("1000"), order, Decimal("100"))
    assert result is not None
    assert result.quantity == Decimal("10")  # clipped to allocation 1000 / price 100


def test_buy_with_no_headroom_is_rejected() -> None:
    # Already fully deployed (qty 10 * price 100 = allocation).
    assert enforce_allocation(_long("10"), Decimal("1000"), _order(FillSide.buy, "5"),
                              Decimal("100")) is None


def test_partial_headroom_clips_to_remainder() -> None:
    # Deployed 6 of a 10-unit cap → 4 units of headroom remain.
    result = enforce_allocation(_long("6"), Decimal("1000"), _order(FillSide.buy, "8"),
                                Decimal("100"))
    assert result is not None
    assert result.quantity == Decimal("4")


def test_sell_is_always_allowed_in_full() -> None:
    order = _order(FillSide.sell, "10")
    result = enforce_allocation(_long("10"), Decimal("1000"), order, Decimal("100"))
    assert result is order  # reducing exposure is never capped


def test_zero_allocation_rejects_new_buys() -> None:
    assert enforce_allocation(_flat(), Decimal("0"), _order(FillSide.buy, "1"),
                              Decimal("100")) is None


def test_zero_allocation_still_allows_closing() -> None:
    order = _order(FillSide.sell, "5")
    result = enforce_allocation(_long("5"), Decimal("0"), order, Decimal("100"))
    assert result is order


def test_non_positive_price_is_rejected() -> None:
    assert enforce_allocation(_flat(), Decimal("1000"), _order(FillSide.buy, "1"),
                              Decimal("0")) is None

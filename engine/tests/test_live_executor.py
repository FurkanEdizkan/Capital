"""Tests for the Live / Testnet executors — hermetic, fake Binance client."""

from decimal import Decimal
from typing import Any

import pytest
from binance.exceptions import BinanceAPIException
from sqlmodel import Session, select

from trading.executors.base import ExecutionError, Order
from trading.executors.live import LiveExecutor
from trading.executors.testnet import TestnetExecutor
from trading.models import FillSide, Trade


class FakeBinance:
    """Canned python-binance `Client` stand-in recording the calls made."""

    def __init__(self, *, reject: bool = False, margin_clash: bool = False) -> None:
        self.reject = reject
        self.margin_clash = margin_clash
        self.calls: list[str] = []
        self.kwargs: dict[str, dict[str, Any]] = {}  # last kwargs per method

    def create_order(self, **kw: Any) -> dict[str, Any]:
        self.calls.append("create_order")
        self.kwargs["create_order"] = kw
        if self.reject:
            raise BinanceAPIException(None, 400, '{"code":-2010,"msg":"rejected"}')
        return {
            "executedQty": "1.0",
            "fills": [
                {"price": "100.0", "qty": "0.5", "commission": "0.05"},
                {"price": "102.0", "qty": "0.5", "commission": "0.051"},
            ],
        }

    def futures_create_order(self, **kw: Any) -> dict[str, Any]:
        self.calls.append("futures_create_order")
        self.kwargs["futures_create_order"] = kw
        return {"avgPrice": "200.0", "executedQty": "2.0"}

    def futures_change_leverage(self, **_: Any) -> dict[str, Any]:
        self.calls.append("futures_change_leverage")
        return {}

    def futures_change_margin_type(self, **_: Any) -> dict[str, Any]:
        self.calls.append("futures_change_margin_type")
        if self.margin_clash:
            raise BinanceAPIException(
                None, 400, '{"code":-4046,"msg":"No need to change margin type."}'
            )
        return {}


def _order(market: str = "spot", side: FillSide = FillSide.buy, qty: str = "1") -> Order:
    return Order(
        strategy="S", market=market, symbol="BTCUSDT", side=side, quantity=Decimal(qty)
    )


def test_spot_market_order_records_a_trade(session: Session) -> None:
    fake = FakeBinance()
    fill = LiveExecutor(fake).execute(session, _order(), reference_price=Decimal("0"))
    # VWAP of the two fills: (100*0.5 + 102*0.5) / 1.0 = 101.
    assert fill.price == Decimal("101.0")
    assert fill.quantity == Decimal("1.0")
    assert fill.fee == Decimal("0.101")
    trades = session.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].mode == "live"


def test_futures_order_configures_leverage_and_margin(session: Session) -> None:
    fake = FakeBinance()
    executor = LiveExecutor(fake, futures_leverage=5, futures_margin_type="ISOLATED")
    fill = executor.execute(session, _order(market="futures"), reference_price=Decimal("0"))
    assert fill.price == Decimal("200.0")
    assert fill.quantity == Decimal("2.0")
    assert fill.fee == Decimal("200.0") * Decimal("2.0") * executor.fee_rate
    assert "futures_change_leverage" in fake.calls
    assert "futures_change_margin_type" in fake.calls


def test_futures_setup_runs_once_per_symbol(session: Session) -> None:
    fake = FakeBinance()
    executor = LiveExecutor(fake, futures_leverage=3)
    executor.execute(session, _order(market="futures"), reference_price=Decimal("0"))
    executor.execute(session, _order(market="futures"), reference_price=Decimal("0"))
    assert fake.calls.count("futures_change_leverage") == 1  # cached after the first


def test_margin_type_clash_is_tolerated(session: Session) -> None:
    fake = FakeBinance(margin_clash=True)
    executor = LiveExecutor(fake, futures_margin_type="ISOLATED")
    # The -4046 "no need to change" error must not abort the order.
    fill = executor.execute(session, _order(market="futures"), reference_price=Decimal("0"))
    assert fill.quantity == Decimal("2.0")


def test_client_order_id_is_sent_and_recorded(session: Session) -> None:
    fake = FakeBinance()
    LiveExecutor(fake).execute(session, _order(), reference_price=Decimal("0"))
    sent = fake.kwargs["create_order"].get("newClientOrderId")
    assert sent  # a clientOrderId was passed to Binance
    trade = session.exec(select(Trade)).first()
    assert trade is not None
    assert trade.client_order_id == sent


def test_below_min_notional_is_rejected(session: Session) -> None:
    # qty 1 * reference 1 = 1, below the default MIN_NOTIONAL of 5.
    executor = LiveExecutor(FakeBinance())
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="1"), reference_price=Decimal("1"))


def test_exchange_rejection_raises_execution_error(session: Session) -> None:
    executor = LiveExecutor(FakeBinance(reject=True))
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(), reference_price=Decimal("0"))


def test_dust_quantity_is_rejected(session: Session) -> None:
    executor = LiveExecutor(FakeBinance())
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="0.0000001"), reference_price=Decimal("0"))


def test_testnet_executor_labels_trades_testnet(session: Session) -> None:
    fill = TestnetExecutor(FakeBinance()).execute(
        session, _order(), reference_price=Decimal("0")
    )
    assert fill.quantity == Decimal("1.0")
    trade = session.exec(select(Trade)).first()
    assert trade is not None
    assert trade.mode == "testnet"

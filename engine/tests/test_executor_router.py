"""Tests for the executor router — venue + mode executor selection."""

from decimal import Decimal
from typing import Any

from sqlmodel import Session

from appsettings.store import (
    TradingMode,
    set_active_venue,
    set_mode,
    set_venue_credentials,
)
from trading.executor_router import ExecutorRouter
from trading.executors.sim import SimExecutor
from trading.executors.venue import VenueExecutor
from venues.base import Instrument, OrderResult, Venue, VenueCandle


class _FakeVenue(Venue):
    """Minimal stand-in venue for routing tests."""

    name = "fake"

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return []

    def price(self, symbol: str) -> Decimal:
        return Decimal("1")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


class _FakeBuilder:
    """Records (name, mode) so the test can assert how the venue was built."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, TradingMode]] = []

    def __call__(self, session: Session, name: str, mode: TradingMode) -> Venue:
        self.calls.append((name, mode))
        return _FakeVenue()


def _binance_keys(session: Session) -> None:
    set_venue_credentials(
        session, "binance", {"api_key": "k", "api_secret": "s"}
    )


def test_sim_mode_returns_the_sim_executor(session: Session) -> None:
    # The default trading mode is Sim — no credentials needed.
    assert isinstance(ExecutorRouter().resolve(session), SimExecutor)


def test_testnet_without_credentials_falls_back_to_sim(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    # No venue credentials configured — must fall back to Sim.
    assert isinstance(ExecutorRouter().resolve(session), SimExecutor)


def test_testnet_with_keys_returns_a_venue_executor(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    _binance_keys(session)
    builder = _FakeBuilder()
    executor = ExecutorRouter(builder=builder).resolve(session)
    assert isinstance(executor, VenueExecutor)
    assert executor.mode == "testnet"
    assert builder.calls == [("binance", TradingMode.testnet)]


def test_live_with_keys_returns_a_live_executor(session: Session) -> None:
    set_mode(session, TradingMode.live)
    _binance_keys(session)
    executor = ExecutorRouter(builder=_FakeBuilder()).resolve(session)
    assert isinstance(executor, VenueExecutor)
    assert executor.mode == "live"


def test_executor_is_cached(session: Session) -> None:
    set_mode(session, TradingMode.live)
    _binance_keys(session)
    builder = _FakeBuilder()
    router = ExecutorRouter(builder=builder)
    assert router.resolve(session) is router.resolve(session)
    assert len(builder.calls) == 1  # built once, then cached


def test_active_venue_is_resolved(session: Session) -> None:
    set_mode(session, TradingMode.live)
    set_active_venue(session, "alpaca")
    set_venue_credentials(session, "alpaca", {"api_key": "k", "api_secret": "s"})
    builder = _FakeBuilder()
    ExecutorRouter(builder=builder).resolve(session)
    assert builder.calls == [("alpaca", TradingMode.live)]


def test_mode_switch_changes_the_executor(session: Session) -> None:
    _binance_keys(session)
    router = ExecutorRouter(builder=_FakeBuilder())
    set_mode(session, TradingMode.sim)
    assert isinstance(router.resolve(session), SimExecutor)
    set_mode(session, TradingMode.testnet)
    assert isinstance(router.resolve(session), VenueExecutor)

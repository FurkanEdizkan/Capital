"""Tests for the executor router — mode-based executor selection."""

from sqlmodel import Session

from appsettings.store import TradingMode, set_binance_keys, set_mode
from trading.executor_router import ExecutorRouter
from trading.executors.live import LiveExecutor
from trading.executors.sim import SimExecutor
from trading.executors.testnet import TestnetExecutor


class _FakeClientFactory:
    """Records calls so the test can assert how the client was built."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    def __call__(self, api_key: str, api_secret: str, testnet: bool) -> object:
        self.calls.append((api_key, api_secret, testnet))
        return object()


def test_sim_mode_returns_the_sim_executor(session: Session) -> None:
    # The default trading mode is Sim — no keys needed.
    assert isinstance(ExecutorRouter().resolve(session), SimExecutor)


def test_testnet_without_keys_falls_back_to_sim(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    # No Binance keys configured — must fall back to Sim, not crash.
    assert isinstance(ExecutorRouter().resolve(session), SimExecutor)


def test_testnet_with_keys_returns_a_testnet_executor(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    set_binance_keys(session, "key", "secret")
    factory = _FakeClientFactory()
    executor = ExecutorRouter(client_factory=factory).resolve(session)
    assert isinstance(executor, TestnetExecutor)
    assert factory.calls == [("key", "secret", True)]  # testnet=True


def test_live_with_keys_returns_a_live_executor(session: Session) -> None:
    set_mode(session, TradingMode.live)
    set_binance_keys(session, "key", "secret")
    factory = _FakeClientFactory()
    executor = ExecutorRouter(client_factory=factory).resolve(session)
    assert isinstance(executor, LiveExecutor)
    assert not isinstance(executor, TestnetExecutor)
    assert factory.calls[0][2] is False  # live → testnet=False


def test_executor_is_cached(session: Session) -> None:
    set_mode(session, TradingMode.live)
    set_binance_keys(session, "key", "secret")
    factory = _FakeClientFactory()
    router = ExecutorRouter(client_factory=factory)
    assert router.resolve(session) is router.resolve(session)
    assert len(factory.calls) == 1  # built once, then cached


def test_mode_switch_changes_the_executor(session: Session) -> None:
    set_binance_keys(session, "key", "secret")
    router = ExecutorRouter(client_factory=_FakeClientFactory())
    set_mode(session, TradingMode.sim)
    assert isinstance(router.resolve(session), SimExecutor)
    set_mode(session, TradingMode.testnet)
    assert isinstance(router.resolve(session), TestnetExecutor)

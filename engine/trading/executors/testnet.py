"""TestnetExecutor — places real orders against Binance Testnet.

Identical to `LiveExecutor` apart from the `mode` label recorded on trades.
The testnet-vs-live difference is the injected python-binance `Client`, which
is built with `testnet=True`; the executor logic is the same either way.
"""

from trading.executors.live import LiveExecutor


class TestnetExecutor(LiveExecutor):
    """Live executor pointed at Binance Testnet — real orders, testnet funds."""

    __test__ = False  # not a pytest test class despite the "Test" name prefix
    mode = "testnet"

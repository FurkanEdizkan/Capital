"""Trading engine — the scheduled loop that ticks strategies.

Each tick evaluates every registered strategy once, sequentially: pull recent
candles, build the strategy's context, ask it for an order, and route the
order through to the executor. APScheduler runs `tick` with `max_instances=1`
so ticks never overlap — they are strictly serialized (see plan: Trading
engine).
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from exchange.client import BinanceClient
from marketdata.cache import refresh_candles
from strategies.base import BaseStrategy, StrategyContext
from trading.executors.base import BaseExecutor
from trading.portfolio import get_allocation, get_or_create_position

log = logging.getLogger("capital.trading.engine")


class TradingEngine:
    """Runs registered strategies on a fixed interval."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        client: BinanceClient,
        executor: BaseExecutor,
        strategies: list[BaseStrategy] | None = None,
        tick_seconds: int = 60,
        candle_limit: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._client = client
        self._executor = executor
        self._strategies: list[BaseStrategy] = list(strategies or [])
        self._tick_seconds = tick_seconds
        self._candle_limit = candle_limit
        self._scheduler: BackgroundScheduler | None = None

    def register(self, strategy: BaseStrategy) -> None:
        self._strategies.append(strategy)

    @property
    def strategies(self) -> list[BaseStrategy]:
        return list(self._strategies)

    def tick(self) -> None:
        """Evaluate every strategy once. A failing strategy never aborts the tick."""
        for strat in list(self._strategies):
            try:
                self._tick_strategy(strat)
            except Exception:  # noqa: BLE001 — isolate per-strategy failures
                log.exception("strategy %r tick failed", strat.name)

    def _tick_strategy(self, strat: BaseStrategy) -> None:
        with self._session_factory() as session:
            candles = refresh_candles(
                session,
                self._client,
                market=strat.market,
                symbol=strat.symbol,
                interval=strat.timeframe,
                limit=self._candle_limit,
            )
            if not candles:
                return
            price = candles[-1].close
            position = get_or_create_position(
                session, strat.name, strat.market.value, strat.symbol
            )
            allocation = get_allocation(session, strat.name)
            ctx = StrategyContext(
                candles=candles,
                position=position,
                allocation=allocation,
                price=price,
            )
            order = strat.evaluate(ctx)
            if order is None:
                return
            # Phase 2: risk checks are pass-through — the full risk manager
            # arrives in Phase 3 (issue #23).
            self._executor.execute(session, order, reference_price=price)
            log.info("strategy %r executed %s %s", strat.name, order.side, order.symbol)

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self.tick,
            trigger="interval",
            seconds=self._tick_seconds,
            max_instances=1,  # ticks are strictly serialized
            coalesce=True,
        )
        self._scheduler.start()
        log.info("trading engine started — %d strategies", len(self._strategies))

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            log.info("trading engine stopped")

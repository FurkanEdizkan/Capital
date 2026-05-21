"""Trading engine — the scheduled loop that ticks strategies.

Each tick evaluates every registered strategy once, sequentially: pull recent
candles, build the strategy's context, ask it for an order, and route the
order through to the executor. APScheduler runs `tick` with `max_instances=1`
so ticks never overlap — they are strictly serialized (see plan: Trading
engine).
"""

import logging
from collections.abc import Callable
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from marketdata.cache import refresh_venue_candles
from marketdata.freshness import feed_is_stale
from notify.telegram import TelegramNotifier
from ops.retention import prune_all
from ops.watchdog import record_heartbeat
from strategies.base import BaseStrategy, StrategyContext
from trading.accounting import record_equity_snapshot
from trading.executor_router import ExecutorRouter
from trading.executors.base import ExecutionError, Order
from trading.lifecycle import is_enabled
from trading.models import FillSide, PositionSide
from trading.portfolio import (
    enforce_allocation,
    get_allocation,
    get_or_create_position,
    list_positions,
)
from trading.risk import RiskManager
from trading.venue_router import VenueRouter

log = logging.getLogger("capital.trading.engine")


class TradingEngine:
    """Runs registered strategies on a fixed interval."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        venue_router: VenueRouter | None = None,
        router: ExecutorRouter | None = None,
        strategies: list[BaseStrategy] | None = None,
        risk: RiskManager | None = None,
        notifier: TelegramNotifier | None = None,
        tick_seconds: int = 60,
        candle_limit: int = 200,
        retention_candle_days: int = 0,
        retention_equity_days: int = 0,
    ) -> None:
        self._session_factory = session_factory
        # Resolves the market-data venue from the active-venue setting per tick.
        self._venue_router = venue_router or VenueRouter.default()
        # Resolves Sim / Testnet / Live executor from the stored mode per tick.
        self._router = router or ExecutorRouter()
        self._risk = risk or RiskManager()  # all limits disabled by default
        self._notifier = notifier or TelegramNotifier()  # disabled by default
        self._strategies: list[BaseStrategy] = list(strategies or [])
        self._tick_seconds = tick_seconds
        self._candle_limit = candle_limit
        self._retention_candle_days = retention_candle_days
        self._retention_equity_days = retention_equity_days
        self._scheduler: BackgroundScheduler | None = None
        # Set on stop() so no new tick begins once shutdown is underway.
        self._stopping = False
        # Latest price seen per symbol — used to mark positions for the
        # equity snapshot recorded at the end of each tick.
        self._last_prices: dict[str, Decimal] = {}

    def register(self, strategy: BaseStrategy) -> None:
        self._strategies.append(strategy)

    @property
    def strategies(self) -> list[BaseStrategy]:
        return list(self._strategies)

    def tick(self) -> None:
        """Evaluate every strategy once, then record an equity snapshot.

        A failing strategy never aborts the tick. Once shutdown is underway no
        new tick begins — the in-flight one is drained by `stop()`.
        """
        if self._stopping:
            return
        for strat in list(self._strategies):
            try:
                self._tick_strategy(strat)
            except Exception:  # noqa: BLE001 — isolate per-strategy failures
                log.exception("strategy %r tick failed", strat.name)
        try:
            with self._session_factory() as session:
                record_equity_snapshot(session, dict(self._last_prices))
                # Heartbeat — the watchdog uses this to detect a stalled loop.
                record_heartbeat(session)
        except Exception:  # noqa: BLE001 — accounting must not abort the loop
            log.exception("equity snapshot failed")

    def _tick_strategy(self, strat: BaseStrategy) -> None:
        with self._session_factory() as session:
            candles = refresh_venue_candles(
                session,
                self._venue_router.resolve(session),
                market=strat.market,
                symbol=strat.symbol,
                interval=strat.timeframe,
                limit=self._candle_limit,
            )
            if not candles:
                return
            # Stale-data safeguard — freeze trading if the feed has stalled,
            # rather than acting (or marking) on frozen prices.
            if feed_is_stale(candles[-1], strat.timeframe):
                log.warning(
                    "feed stale for %s %s — trading frozen this tick",
                    strat.symbol,
                    strat.timeframe,
                )
                return
            price = candles[-1].close
            self._last_prices[strat.symbol] = price
            position = get_or_create_position(
                session, strat.name, strat.market.value, strat.symbol
            )
            # Route orders through the executor for the active trading mode.
            executor = self._router.resolve(session)
            # Risk: force-close a position that breached its stop-loss or
            # take-profit. This runs regardless of lifecycle state — a stop is
            # a safety net, not a strategy-driven entry.
            stop = self._risk.stop_order(position, price)
            if stop is not None:
                executor.execute(session, stop, reference_price=price)
                log.info("risk: stopped out %r position on %s", strat.name, strat.symbol)
                return
            # Lifecycle: a disabled strategy is skipped — no new entries — but
            # its open positions are left intact for a manual close.
            if not is_enabled(session, strat.name):
                return
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
            # Cap the order to the strategy's capital allocation. The full risk
            # manager (sizing, SL/TP, kill switch) arrives in issue #23.
            order = enforce_allocation(position, allocation, order, price)
            if order is None:
                log.info("strategy %r order rejected — allocation exhausted", strat.name)
                return
            # Risk: order sizing cap + kill switch (blocks new exposure only).
            order = self._risk.review(session, order, position, price)
            if order is None:
                log.info("strategy %r order blocked by risk manager", strat.name)
                return
            try:
                fill = executor.execute(session, order, reference_price=price)
            except ExecutionError as exc:
                log.info("strategy %r order skipped: %s", strat.name, exc)
                return
            log.info("strategy %r executed %s %s", strat.name, order.side, order.symbol)
            self._notifier.send(
                f"Trade — {strat.name}: {fill.side.value} "
                f"{fill.quantity} {fill.symbol} @ {fill.price}"
            )

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._stopping = False
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self.tick,
            trigger="interval",
            seconds=self._tick_seconds,
            max_instances=1,  # ticks are strictly serialized
            coalesce=True,
        )
        if self._retention_candle_days > 0 or self._retention_equity_days > 0:
            # Daily retention prune at 04:00 — keeps the database bounded.
            self._scheduler.add_job(self._prune, trigger="cron", hour=4, id="retention")
        self._scheduler.start()
        log.info("trading engine started — %d strategies", len(self._strategies))

    def _prune(self) -> None:
        """Scheduled retention prune of old candles and equity snapshots."""
        try:
            with self._session_factory() as session:
                prune_all(
                    session,
                    candle_days=self._retention_candle_days,
                    equity_days=self._retention_equity_days,
                )
        except Exception:  # noqa: BLE001 — retention must not abort the engine
            log.exception("retention prune failed")

    def stop(self, *, wait: bool = True) -> None:
        """Stop the engine.

        With `wait=True` (the default) this blocks until the in-flight tick
        has finished — a graceful shutdown, so a SIGTERM from a redeploy never
        interrupts an order mid-flight. Setting `_stopping` first ensures no
        new tick begins while the current one drains.
        """
        self._stopping = True
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=wait)
            self._scheduler = None
            log.info("trading engine stopped (drained=%s)", wait)

    def flatten(self, strategy: str) -> int:
        """Close every open position held by `strategy`. Returns the count closed.

        Backs the manual-close action on the Strategies page — e.g. flattening
        a disabled strategy before removing it. Positions are closed at the
        last price seen for the symbol, falling back to the entry price.
        """
        closed = 0
        with self._session_factory() as session:
            executor = self._router.resolve(session)
            for pos in list_positions(session, strategy=strategy, open_only=True):
                price = self._last_prices.get(pos.symbol, pos.entry_price)
                side = (
                    FillSide.sell
                    if pos.side == PositionSide.long.value
                    else FillSide.buy
                )
                order = Order(
                    strategy=strategy,
                    market=pos.market,
                    symbol=pos.symbol,
                    side=side,
                    quantity=pos.qty,
                )
                try:
                    executor.execute(session, order, reference_price=price)
                    closed += 1
                except ExecutionError:
                    log.warning(
                        "could not flatten %r position on %s", strategy, pos.symbol
                    )
        return closed

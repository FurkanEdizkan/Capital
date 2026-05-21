"""Capital trading engine — FastAPI application entry point.

Mounts the API routers and, on startup, seeds the admin operator, starts the
live market-data streams and the paper-trading engine.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from api.ai import router as ai_router
from api.backtest import router as backtest_router
from api.history import router as history_router
from api.market import router as market_router
from api.market import ws_router as market_ws_router
from api.portfolio import router as portfolio_router
from api.settings import router as settings_router
from api.strategies import router as strategies_router
from api.system import router as system_router
from api.tokens import router as tokens_router
from api.users import router as users_router
from api.venues import router as venues_router
from auth.routes import router as auth_router
from auth.seed import seed_admin
from config import settings
from db import engine as db_engine
from logging_config import setup_logging
from marketdata.stream import StreamManager
from notify.telegram import TelegramNotifier
from ops.recovery import recover_on_boot
from strategies.builtin import all_strategies, seed_allocations
from trading.engine import TradingEngine
from trading.executor_router import ExecutorRouter
from trading.risk import RiskManager

setup_logging(settings.log_level)
log = logging.getLogger("capital")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    try:
        seed_admin()
    except Exception:  # noqa: BLE001 — never let seeding crash startup
        log.exception("Admin seeding skipped (run `alembic upgrade head` first?)")

    # Live market-data streams — self-healing Binance WebSocket consumers.
    streams = StreamManager()
    app.state.streams = streams
    streams.start()

    # Paper-trading engine — ticks the built-in strategies on a schedule.
    def session_factory() -> Session:
        return Session(db_engine)

    # Boot recovery — reconcile open positions with Binance before trading.
    try:
        with session_factory() as session:
            recover_on_boot(session)
    except Exception:  # noqa: BLE001 — recovery must not block startup
        log.exception("Boot recovery skipped")

    strategies = all_strategies()
    try:
        seed_allocations(session_factory, strategies)
    except Exception:  # noqa: BLE001 — never let seeding crash startup
        log.exception("Strategy allocation seeding skipped")
    trading = TradingEngine(
        session_factory=session_factory,
        router=ExecutorRouter(),
        strategies=strategies,
        risk=RiskManager.from_settings(settings),
        notifier=TelegramNotifier.from_settings(settings),
        retention_candle_days=settings.retention_candle_days,
        retention_equity_days=settings.retention_equity_days,
    )
    app.state.trading = trading
    trading.start()

    try:
        yield
    finally:
        trading.stop()
        await streams.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="Self-hosted automated Binance trading engine.",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(market_router)
app.include_router(market_ws_router)
app.include_router(portfolio_router)
app.include_router(strategies_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(history_router)
app.include_router(ai_router)
app.include_router(tokens_router)
app.include_router(venues_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe — used by Docker, CI and the deploy script."""
    return {
        "status": "ok",
        "service": "capital-engine",
        "version": settings.version,
        "environment": settings.environment,
    }


def main() -> None:
    """Run the engine with uvicorn (``python main.py`` / container CMD)."""
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()

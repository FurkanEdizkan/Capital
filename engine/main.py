"""Capital trading engine — FastAPI application entry point.

Mounts the API routers and seeds the initial admin on startup. Later phases
add the market-data, trading, strategy and MCP routers.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.users import router as users_router
from auth.routes import router as auth_router
from auth.seed import seed_admin
from config import settings
from marketdata.stream import StreamManager

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
    try:
        yield
    finally:
        await streams.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="Self-hosted automated Binance trading engine.",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(users_router)


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

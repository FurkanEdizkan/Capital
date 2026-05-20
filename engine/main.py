"""Capital trading engine — FastAPI application entry point.

Phase 0 scope: a health endpoint and the app skeleton. Later phases mount the
market-data, trading, strategy, auth and MCP routers onto this app.
"""

from fastapi import FastAPI

from config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="Self-hosted automated Binance trading engine.",
)


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

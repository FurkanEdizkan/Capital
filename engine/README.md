# Capital — Engine

The trading engine: a FastAPI service and (in later phases) the 24/7 bot.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Develop

```bash
uv sync              # create .venv and install dependencies from uv.lock
uv run uvicorn main:app --reload   # run the API at http://localhost:8000
uv run pytest        # run tests
uv run ruff check .  # lint
```

Health check: `GET /health`.

## Layout

Flat application layout — modules live directly under `engine/`. Later phases
add `binance/`, `trading/`, `strategies/`, `api/`, `auth/`, `ai/` packages.

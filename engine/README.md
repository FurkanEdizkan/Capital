# Capital — Engine

The trading engine: a FastAPI service and (in later phases) the 24/7 bot.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker (for PostgreSQL)

## Develop

```bash
# From the repo root: start PostgreSQL.
docker compose up -d postgres

# In engine/:
uv sync                            # create .venv, install from uv.lock
uv run alembic upgrade head        # apply database migrations
uv run uvicorn main:app --reload   # run the API at http://localhost:8000
uv run pytest                      # run tests
uv run ruff check .                # lint
```

Health check: `GET /health`.

## Database

PostgreSQL via SQLModel; schema changes are managed **only** through Alembic
migrations (`engine/alembic/`):

```bash
uv run alembic revision --autogenerate -m "add X"   # create a migration
uv run alembic upgrade head                          # apply
uv run alembic downgrade -1                          # roll back one
```

## Layout

Flat application layout — modules live directly under `engine/`. Later phases
add `binance/`, `trading/`, `strategies/`, `api/`, `auth/`, `ai/` packages.

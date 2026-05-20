"""Database layer — SQLModel engine + session management.

A single shared SQLAlchemy engine backs both the FastAPI request handlers
(via the `get_session` dependency) and the trading loop. Schema changes are
managed exclusively through Alembic migrations — see `engine/alembic/`.
"""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from config import settings

# `pool_pre_ping` recycles dropped connections — important for a 24/7 process.
engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session


__all__ = ["SQLModel", "engine", "get_session"]

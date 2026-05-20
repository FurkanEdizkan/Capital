"""Engine configuration — loaded from environment / .env via pydantic-settings.

This is the single source of truth for runtime config. Later phases extend
`Settings` with Binance keys, the JWT secret, etc.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CAPITAL_",
        extra="ignore",
    )

    app_name: str = "Capital Engine"
    version: str = "0.1.0"
    environment: str = "development"

    # PostgreSQL connection (SQLAlchemy URL, psycopg3 driver). Override via
    # CAPITAL_DATABASE_URL; the default targets the local docker-compose Postgres.
    database_url: str = "postgresql+psycopg://capital:capital@localhost:5432/capital"


settings = Settings()

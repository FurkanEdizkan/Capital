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

    # --- Auth -------------------------------------------------------------
    # JWT signing secret. MUST be overridden in any real deployment via
    # CAPITAL_JWT_SECRET — the default is for local development only.
    jwt_secret: str = "dev-insecure-jwt-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # Seeded admin operator — created on first startup if no users exist.
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # Login rate limiting (brute-force protection).
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15


settings = Settings()

"""Engine configuration — loaded from environment / .env via pydantic-settings.

This is the single source of truth for runtime config. Later phases extend
`Settings` with Binance keys, the JWT secret, etc.
"""

from decimal import Decimal

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

    # Directory scanned for custom code-strategy plugins (see strategies/loader.py).
    # Relative paths resolve against the engine working directory.
    strategy_plugins_dir: str = "strategies/plugins"

    # PostgreSQL connection (SQLAlchemy URL, psycopg3 driver). Override via
    # CAPITAL_DATABASE_URL; the default targets the local docker-compose Postgres.
    database_url: str = "postgresql+psycopg://capital:capital@localhost:5432/capital"

    # --- Auth -------------------------------------------------------------
    # JWT signing secret. MUST be overridden in any real deployment via
    # CAPITAL_JWT_SECRET — the default is for local development only.
    jwt_secret: str = "dev-insecure-jwt-secret-change-me-in-production"

    # Secret-encryption key — encrypts Binance/LLM API keys stored in the DB.
    # MUST be overridden via CAPITAL_SECRET_KEY; without the exact key a DB
    # restore cannot decrypt the stored credentials. Any string works (it is
    # hashed into a Fernet key).
    secret_key: str = "dev-insecure-secret-key-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # Seeded admin operator — created on first startup if no users exist.
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # Login rate limiting (brute-force protection).
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # --- Risk manager -----------------------------------------------------
    # Global trading limits enforced by trading/risk.py. Every limit is 0 by
    # default, meaning *disabled* — risk control is strictly opt-in.
    #
    # Max notional value of any single order (quote currency).
    risk_max_position_notional: Decimal = Decimal(0)
    # Force-close a position when its unrealized loss/gain reaches this percent
    # of the position's entry value.
    risk_stop_loss_pct: Decimal = Decimal(0)
    risk_take_profit_pct: Decimal = Decimal(0)
    # Kill switch — halt new exposure when the day's realized loss (quote
    # currency) or the equity drawdown from peak (percent) exceeds the limit.
    risk_daily_loss_limit: Decimal = Decimal(0)
    risk_max_drawdown_pct: Decimal = Decimal(0)


settings = Settings()

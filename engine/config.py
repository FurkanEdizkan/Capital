"""Engine configuration — loaded from environment / .env via pydantic-settings.

This is the single source of truth for runtime config. Later phases extend
`Settings` with the database URL, Binance keys, JWT secret, etc.
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


settings = Settings()

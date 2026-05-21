"""Database model for runtime settings.

A simple key/value table holding the trading mode and the encrypted Binance
API credentials. Secret values are encrypted before storage (see crypto.py);
the `is_secret` flag records which rows are ciphertext.
"""

from sqlmodel import Field, SQLModel


class Setting(SQLModel, table=True):
    """One runtime setting. Secret values are stored as ciphertext."""

    __tablename__ = "setting"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=64)
    value: str = Field(default="")
    is_secret: bool = Field(default=False)

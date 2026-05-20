"""Market-data database models — the OHLCV candle cache.

Candles fetched from Binance are cached here so charts, indicators and
backtests read from PostgreSQL instead of hammering the exchange. A closed
candle is immutable, so rows are insert-only and deduplicated on
(market, symbol, interval, open_time).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

# Numeric precision for crypto prices/volumes.
_PRICE = {"max_digits": 24, "decimal_places": 8}


class Candle(SQLModel, table=True):
    """A single OHLCV bar for one symbol/interval/market."""

    __tablename__ = "candle"
    __table_args__ = (
        UniqueConstraint(
            "market", "symbol", "interval", "open_time", name="uq_candle_bar"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market: str = Field(max_length=8, index=True)
    symbol: str = Field(max_length=24, index=True)
    interval: str = Field(max_length=8, index=True)
    open_time: datetime = Field(index=True)
    open: Decimal = Field(**_PRICE)
    high: Decimal = Field(**_PRICE)
    low: Decimal = Field(**_PRICE)
    close: Decimal = Field(**_PRICE)
    volume: Decimal = Field(**_PRICE)
    close_time: datetime

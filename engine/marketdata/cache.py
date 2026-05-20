"""Candle cache — fetches OHLCV bars from Binance and caches them in Postgres.

Closed candles are immutable, so the cache is insert-only: a refresh fetches
the latest bars and inserts only those not already stored.
"""

from datetime import UTC, datetime

from sqlmodel import Session, select

from exchange.client import BinanceClient, Market
from marketdata.models import Candle


def _naive_utc(dt: datetime) -> datetime:
    """Normalise to naive UTC — candle timestamps are stored tz-naive (UTC)
    so equality holds consistently across PostgreSQL and SQLite."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def get_cached_candles(
    session: Session,
    *,
    market: Market,
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[Candle]:
    """Return up to `limit` most-recent cached candles, oldest-first."""
    rows = session.exec(
        select(Candle)
        .where(
            Candle.market == market.value,
            Candle.symbol == symbol,
            Candle.interval == interval,
        )
        .order_by(Candle.open_time.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    return list(reversed(rows))


def refresh_candles(
    session: Session,
    client: BinanceClient,
    *,
    market: Market,
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[Candle]:
    """Fetch the latest candles from Binance, cache new ones, return the series."""
    fetched = client.get_klines(symbol, interval, market, limit)

    existing = set(
        session.exec(
            select(Candle.open_time).where(
                Candle.market == market.value,
                Candle.symbol == symbol,
                Candle.interval == interval,
            )
        ).all()
    )

    new_rows = [
        Candle(
            market=market.value,
            symbol=symbol,
            interval=interval,
            open_time=_naive_utc(k.open_time),
            open=k.open,
            high=k.high,
            low=k.low,
            close=k.close,
            volume=k.volume,
            close_time=_naive_utc(k.close_time),
        )
        for k in fetched
        if _naive_utc(k.open_time) not in existing
    ]
    if new_rows:
        session.add_all(new_rows)
        session.commit()

    return get_cached_candles(
        session, market=market, symbol=symbol, interval=interval, limit=limit
    )

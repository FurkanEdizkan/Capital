"""Candle cache — fetches OHLCV bars from Binance and caches them in Postgres.

Closed candles are immutable, so the cache is insert-only: a refresh fetches
the latest bars and inserts only those not already stored.
"""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from exchange.client import BinanceClient, Market
from marketdata.freshness import interval_seconds
from marketdata.models import Candle
from venues.base import Venue


def _naive_utc(dt: datetime) -> datetime:
    """Normalise to naive UTC — candle timestamps are stored tz-naive (UTC)
    so equality holds consistently across PostgreSQL and SQLite."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _to_candle(market: Market, symbol: str, interval: str, k: object) -> Candle:
    """Build a `Candle` row from an exchange `Kline`."""
    return Candle(
        market=market.value,
        symbol=symbol,
        interval=interval,
        open_time=_naive_utc(k.open_time),  # type: ignore[attr-defined]
        open=k.open,  # type: ignore[attr-defined]
        high=k.high,  # type: ignore[attr-defined]
        low=k.low,  # type: ignore[attr-defined]
        close=k.close,  # type: ignore[attr-defined]
        volume=k.volume,  # type: ignore[attr-defined]
        close_time=_naive_utc(k.close_time),  # type: ignore[attr-defined]
    )


def _existing_open_times(
    session: Session, *, market: Market, symbol: str, interval: str
) -> set[datetime]:
    """The set of `open_time`s already cached for this market/symbol/interval."""
    return set(
        session.exec(
            select(Candle.open_time).where(
                Candle.market == market.value,
                Candle.symbol == symbol,
                Candle.interval == interval,
            )
        ).all()
    )


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


def get_candle_range(
    session: Session,
    *,
    market: Market,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime | None = None,
) -> list[Candle]:
    """Cached candles with `open_time` in ``[start, end]``, oldest-first."""
    query = select(Candle).where(
        Candle.market == market.value,
        Candle.symbol == symbol,
        Candle.interval == interval,
        Candle.open_time >= _naive_utc(start),
    )
    if end is not None:
        query = query.where(Candle.open_time <= _naive_utc(end))
    return list(session.exec(query.order_by(Candle.open_time)).all())  # type: ignore[arg-type]


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
    existing = _existing_open_times(
        session, market=market, symbol=symbol, interval=interval
    )
    new_rows = [
        _to_candle(market, symbol, interval, k)
        for k in fetched
        if _naive_utc(k.open_time) not in existing
    ]
    if new_rows:
        session.add_all(new_rows)
        session.commit()

    return get_cached_candles(
        session, market=market, symbol=symbol, interval=interval, limit=limit
    )


def refresh_venue_candles(
    session: Session,
    venue: Venue,
    *,
    market: Market,
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[Candle]:
    """Fetch the latest candles from a `Venue`, cache new ones, return the series.

    The venue-neutral equivalent of `refresh_candles`. `VenueCandle` carries no
    close time, so it is derived from the open time plus the interval length.
    """
    fetched = venue.candles(symbol, interval, limit)
    existing = _existing_open_times(
        session, market=market, symbol=symbol, interval=interval
    )
    span = timedelta(seconds=interval_seconds(interval))
    new_rows: list[Candle] = []
    for bar in fetched:
        open_time = _naive_utc(bar.open_time)
        if open_time in existing:
            continue
        new_rows.append(
            Candle(
                market=market.value,
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                close_time=open_time + span - timedelta(milliseconds=1),
            )
        )
    if new_rows:
        session.add_all(new_rows)
        session.commit()

    return get_cached_candles(
        session, market=market, symbol=symbol, interval=interval, limit=limit
    )


def download_candles(
    session: Session,
    client: BinanceClient,
    *,
    market: Market,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime | None = None,
) -> int:
    """Download historical klines for ``[start, end]`` and cache new ones.

    Returns the number of newly-inserted candles. The cache is insert-only, so
    re-downloading an already-cached range is a cheap no-op. Backs the backtest
    history downloader.
    """
    fetched = client.get_historical_klines(
        symbol, interval, start=start, end=end, market=market
    )
    existing = _existing_open_times(
        session, market=market, symbol=symbol, interval=interval
    )
    new_rows = [
        _to_candle(market, symbol, interval, k)
        for k in fetched
        if _naive_utc(k.open_time) not in existing
    ]
    if new_rows:
        session.add_all(new_rows)
        session.commit()
    return len(new_rows)

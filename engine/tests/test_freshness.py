"""Tests for the stale-data safeguard."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from marketdata.freshness import feed_is_stale, interval_seconds
from marketdata.models import Candle

_NOW = datetime(2026, 5, 21, 12, 0, 0)


def _candle(open_time: datetime, interval: str = "1h") -> Candle:
    return Candle(
        market="spot",
        symbol="BTCUSDT",
        interval=interval,
        open_time=open_time,
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        close_time=open_time + timedelta(minutes=59),
    )


def test_interval_seconds() -> None:
    assert interval_seconds("1m") == 60
    assert interval_seconds("15m") == 900
    assert interval_seconds("1h") == 3600
    assert interval_seconds("4h") == 14_400
    assert interval_seconds("1d") == 86_400
    assert interval_seconds("1w") == 604_800
    assert interval_seconds("1M") == 2_592_000


def test_interval_seconds_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        interval_seconds("banana")
    with pytest.raises(ValueError):
        interval_seconds("1y")


def test_recent_candle_is_fresh() -> None:
    # The newest candle opened an hour ago — normal for a 1h feed.
    candle = _candle(_NOW - timedelta(hours=1))
    assert feed_is_stale(candle, "1h", now=_NOW) is False


def test_old_candle_is_stale() -> None:
    # Five hours behind on a 1h feed — the feed has clearly stalled.
    candle = _candle(_NOW - timedelta(hours=5))
    assert feed_is_stale(candle, "1h", now=_NOW) is True


def test_staleness_threshold_scales_with_interval() -> None:
    # Three hours old: stale for a 1h feed, fresh for a 4h feed.
    candle = _candle(_NOW - timedelta(hours=3))
    assert feed_is_stale(candle, "1h", now=_NOW) is True
    assert feed_is_stale(candle, "4h", now=_NOW) is False

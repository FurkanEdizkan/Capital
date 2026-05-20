"""Tests for the hand-rolled technical indicators."""

from decimal import Decimal

import pytest

from strategies.indicators import bollinger, ema, ema_series, macd, rsi, sma


def _d(values: list[float]) -> list[Decimal]:
    return [Decimal(str(v)) for v in values]


def test_sma_averages_the_last_period() -> None:
    assert sma(_d([1, 2, 3, 4, 5]), 3) == Decimal(4)  # (3+4+5)/3


def test_sma_rejects_short_series() -> None:
    with pytest.raises(ValueError):
        sma(_d([1, 2]), 3)


def test_ema_series_length_and_seed() -> None:
    series = ema_series(_d([1, 2, 3, 4, 5]), 3)
    assert len(series) == 3  # len - period + 1
    assert series[0] == Decimal(2)  # seeded with SMA of the first 3 values


def test_ema_tracks_a_constant_series() -> None:
    assert ema(_d([5] * 10), 4) == Decimal(5)


def test_rsi_is_100_when_only_gains() -> None:
    assert rsi(_d(list(range(1, 20))), 14) == Decimal(100)


def test_rsi_is_0_when_only_losses() -> None:
    assert rsi(_d(list(range(20, 1, -1))), 14) == Decimal(0)


def test_rsi_is_mid_range_for_balanced_swings() -> None:
    # Alternating up/down by the same amount → roughly balanced → RSI near 50.
    closes = _d([10, 11] * 12)
    assert Decimal(40) < rsi(closes, 14) < Decimal(60)


def test_rsi_rejects_short_series() -> None:
    with pytest.raises(ValueError):
        rsi(_d([1, 2, 3]), 14)


def test_macd_positive_on_uptrend() -> None:
    macd_line, signal_line, hist = macd(_d(list(range(1, 60))))
    assert macd_line > 0  # fast EMA leads slow EMA on a steady rise
    assert hist == macd_line - signal_line


def test_macd_negative_on_downtrend() -> None:
    macd_line, _, _ = macd(_d(list(range(60, 1, -1))))
    assert macd_line < 0


def test_macd_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError):
        macd(_d(list(range(1, 60))), fast=26, slow=26)


def test_bollinger_bands_are_ordered() -> None:
    lower, mid, upper = bollinger(_d([1, 2, 3, 4, 5, 6, 7, 8]), period=8)
    assert lower < mid < upper
    assert mid == Decimal("4.5")  # SMA of 1..8


def test_bollinger_collapses_on_constant_series() -> None:
    lower, mid, upper = bollinger(_d([100] * 20), period=20)
    assert lower == mid == upper == Decimal(100)  # zero variance

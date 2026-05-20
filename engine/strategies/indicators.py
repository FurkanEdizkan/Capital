"""Technical indicators over `Decimal` price series.

Hand-rolled — no `pandas` / `pandas-ta` — so the engine stays light and the
maths is explicit and unit-testable. Every function takes an oldest-first list
of closing prices and raises `ValueError` when there is not enough history.
"""

from decimal import Decimal


def sma(values: list[Decimal], period: int) -> Decimal:
    """Simple moving average of the last `period` values."""
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for the requested period")
    window = values[-period:]
    return sum(window, Decimal(0)) / Decimal(period)


def ema_series(values: list[Decimal], period: int) -> list[Decimal]:
    """Exponential moving average series, seeded with the first SMA.

    Emits one value per input from index `period - 1` onward, so the result
    has length `len(values) - period + 1`.
    """
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for the requested period")
    k = Decimal(2) / Decimal(period + 1)
    seed = sum(values[:period], Decimal(0)) / Decimal(period)
    out = [seed]
    for v in values[period:]:
        out.append(v * k + out[-1] * (Decimal(1) - k))
    return out


def ema(values: list[Decimal], period: int) -> Decimal:
    """Latest exponential moving average value."""
    return ema_series(values, period)[-1]


def rsi(values: list[Decimal], period: int = 14) -> Decimal:
    """Wilder's Relative Strength Index — a 0..100 momentum oscillator."""
    if period <= 0 or len(values) < period + 1:
        raise ValueError("not enough values for the requested period")
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for prev, cur in zip(values[:-1], values[1:], strict=True):
        delta = cur - prev
        gains.append(delta if delta > 0 else Decimal(0))
        losses.append(-delta if delta < 0 else Decimal(0))
    # Wilder smoothing: seed with the simple average, then roll it forward.
    avg_gain = sum(gains[:period], Decimal(0)) / Decimal(period)
    avg_loss = sum(losses[:period], Decimal(0)) / Decimal(period)
    for g, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + g) / Decimal(period)
        avg_loss = (avg_loss * (period - 1) + loss) / Decimal(period)
    if avg_loss == 0:
        return Decimal(100)
    rs = avg_gain / avg_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + rs)


def macd(
    values: list[Decimal],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[Decimal, Decimal, Decimal]:
    """MACD line, signal line and histogram (latest values).

    MACD line = EMA(fast) − EMA(slow); signal = EMA(MACD line, signal);
    histogram = MACD line − signal. Needs `slow + signal - 1` values.
    """
    if fast >= slow:
        raise ValueError("fast period must be shorter than slow period")
    fast_s = ema_series(values, fast)
    slow_s = ema_series(values, slow)
    # The slow EMA series starts `slow - fast` samples later — align them.
    offset = len(fast_s) - len(slow_s)
    macd_line = [f - s for f, s in zip(fast_s[offset:], slow_s, strict=True)]
    signal_line = ema_series(macd_line, signal)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return macd_val, signal_val, macd_val - signal_val


def bollinger(
    values: list[Decimal],
    period: int = 20,
    num_std: Decimal = Decimal(2),
) -> tuple[Decimal, Decimal, Decimal]:
    """Bollinger bands — `(lower, middle, upper)` over the last `period` values.

    The middle band is the SMA; the outer bands sit `num_std` population
    standard deviations away.
    """
    if period <= 0 or len(values) < period:
        raise ValueError("not enough values for the requested period")
    window = values[-period:]
    mid = sum(window, Decimal(0)) / Decimal(period)
    variance = sum((v - mid) ** 2 for v in window) / Decimal(period)
    std = variance.sqrt()
    return mid - num_std * std, mid, mid + num_std * std

"""Strategy type registry — every classic type, constructible from the UI.

Each entry maps a type key (`ma_cross`, `rsi`, …) to its class and the typed
parameter specs mirroring the constructor keywords, so the API can expose a
schema and the UI can render a form with sane defaults and bounds.
`build_strategy` is the one constructor used for stored instances and ad-hoc
backtest grids: it validates and coerces params before instantiating.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from exchange.client import Market
from marketdata.freshness import interval_seconds
from strategies.base import BaseStrategy
from strategies.bollinger import BollingerStrategy
from strategies.dca import DCAStrategy
from strategies.ma_cross import MACrossStrategy
from strategies.macd import MACDStrategy
from strategies.rsi import RSIStrategy


@dataclass(frozen=True)
class ParamSpec:
    """One constructor keyword — its type, default and accepted range."""

    name: str
    type: str  # "int" | "decimal"
    default: str
    min: str
    max: str
    label: str = ""


@dataclass(frozen=True)
class StrategyType:
    """One pickable strategy type."""

    key: str
    label: str
    cls: type[BaseStrategy]
    params: tuple[ParamSpec, ...]


STRATEGY_TYPES: dict[str, StrategyType] = {
    t.key: t
    for t in (
        StrategyType(
            key="ma_cross",
            label="MA Crossover",
            cls=MACrossStrategy,
            params=(
                ParamSpec("fast", "int", "9", "2", "200", "Fast SMA period"),
                ParamSpec("slow", "int", "21", "3", "400", "Slow SMA period"),
            ),
        ),
        StrategyType(
            key="rsi",
            label="RSI Mean-Reversion",
            cls=RSIStrategy,
            params=(
                ParamSpec("period", "int", "14", "2", "100", "RSI period"),
                ParamSpec("oversold", "decimal", "30", "1", "50", "Oversold level"),
                ParamSpec("overbought", "decimal", "70", "50", "99", "Overbought level"),
            ),
        ),
        StrategyType(
            key="macd",
            label="MACD Trend",
            cls=MACDStrategy,
            params=(
                ParamSpec("fast", "int", "12", "2", "100", "Fast EMA period"),
                ParamSpec("slow", "int", "26", "3", "200", "Slow EMA period"),
                ParamSpec("signal", "int", "9", "2", "100", "Signal period"),
            ),
        ),
        StrategyType(
            key="bollinger",
            label="Bollinger Breakout",
            cls=BollingerStrategy,
            params=(
                ParamSpec("period", "int", "20", "5", "200", "Band period"),
                ParamSpec("num_std", "decimal", "2", "0.5", "4", "Std deviations"),
            ),
        ),
        StrategyType(
            key="dca",
            label="DCA Accumulate",
            cls=DCAStrategy,
            params=(
                ParamSpec("tranche", "decimal", "0.1", "0.01", "1", "Tranche fraction"),
            ),
        ),
    )
}

#: Timeframes an instance may run on (Binance kline intervals).
TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")


def coerce_params(type_key: str, raw: dict) -> dict:
    """Validate `raw` against the type's specs; returns constructor kwargs.

    Unknown keys are rejected; missing keys fall back to the spec default;
    values outside the spec's range raise `ValueError`.
    """
    spec = STRATEGY_TYPES.get(type_key)
    if spec is None:
        raise ValueError(f"unknown strategy type: {type_key!r}")
    known = {p.name: p for p in spec.params}
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"unknown params for {type_key}: {sorted(unknown)}")
    kwargs: dict = {}
    for param in spec.params:
        value = raw.get(param.name, param.default)
        try:
            if param.type == "int":
                coerced: int | Decimal = int(str(value))
            else:
                coerced = Decimal(str(value))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(
                f"param {param.name!r} must be a {param.type}"
            ) from exc
        if not Decimal(param.min) <= Decimal(coerced) <= Decimal(param.max):
            raise ValueError(
                f"param {param.name!r} must be between {param.min} and {param.max}"
            )
        kwargs[param.name] = coerced
    return kwargs


def build_strategy(
    type_key: str,
    *,
    name: str,
    symbol: str,
    market: str = "spot",
    timeframe: str = "1h",
    params: dict | None = None,
) -> BaseStrategy:
    """Instantiate a strategy type with validated params.

    Raises `ValueError` on an unknown type, bad market/timeframe or
    out-of-range params (constructor invariants — e.g. fast < slow — also
    surface as `ValueError`).
    """
    spec = STRATEGY_TYPES.get(type_key)
    if spec is None:
        raise ValueError(f"unknown strategy type: {type_key!r}")
    if timeframe not in TIMEFRAMES:
        interval_seconds(timeframe)  # raises ValueError on a bad format
    kwargs = coerce_params(type_key, params or {})
    return spec.cls(
        name,
        symbol.upper(),
        market=Market(market),
        timeframe=timeframe,
        **kwargs,
    )

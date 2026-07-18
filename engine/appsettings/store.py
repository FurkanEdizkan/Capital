"""Runtime-settings store — trading mode and encrypted venue credentials.

`config.Settings` holds static process config; this module holds settings an
operator changes at runtime through the Settings page, persisted in the DB.

Venue credentials are stored per-venue, one encrypted row per field, keyed
`venue:{venue}:{field}` — so each venue declares its own credential shape
(Binance: api_key+api_secret).
"""

import json
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from sqlmodel import Session, select

from appsettings.crypto import decrypt, encrypt
from appsettings.models import Setting


class TradingMode(StrEnum):
    """Where orders are routed. Sim is the safe default."""

    sim = "sim"
    testnet = "testnet"
    live = "live"


_MODE_KEY = "trading_mode"
_ACTIVE_VENUE_KEY = "active_venue"
_AI_PROVIDER = "ai_provider"
_AI_MODEL = "ai_model"
_AI_BASE_URL = "ai_base_url"
_AI_API_KEY = "ai_api_key"
_AI_SPEND_CAP = "ai_spend_cap_usd"
_AI_ACTION_MODE = "ai_action_mode"
_RISK_STOP_LOSS = "risk_stop_loss_pct"
_RISK_TAKE_PROFIT = "risk_take_profit_pct"
_RISK_MAX_DRAWDOWN = "risk_max_drawdown_pct"
_RISK_DAILY_LOSS = "risk_daily_loss_limit"
_RISK_MAX_NOTIONAL = "risk_max_position_notional"

#: How an AI strategy's decision is applied. `notify` (the default) surfaces it
#: for operator confirmation; `auto` executes it straight through the risk gate.
AI_ACTION_MODES: tuple[str, ...] = ("notify", "auto")


def _get(session: Session, key: str) -> Setting | None:
    return session.exec(select(Setting).where(Setting.key == key)).first()


def _put(session: Session, key: str, value: str, *, is_secret: bool = False) -> None:
    row = _get(session, key)
    stored = encrypt(value) if is_secret else value
    if row is None:
        row = Setting(key=key, value=stored, is_secret=is_secret)
    else:
        row.value = stored
        row.is_secret = is_secret
    session.add(row)
    session.commit()


def get_setting(session: Session, key: str) -> str | None:
    """Read a plain (non-secret) setting value, or None if unset."""
    row = _get(session, key)
    return row.value if row is not None else None


def set_setting(session: Session, key: str, value: str) -> None:
    """Write a plain (non-secret) setting value."""
    _put(session, key, value)


def get_mode(session: Session) -> TradingMode:
    """The active trading mode — defaults to Sim until explicitly changed."""
    row = _get(session, _MODE_KEY)
    return TradingMode(row.value) if row else TradingMode.sim


def set_mode(session: Session, mode: TradingMode) -> None:
    _put(session, _MODE_KEY, mode.value)


def get_active_venue(session: Session) -> str:
    """The venue the engine trades through — defaults to Binance."""
    return get_setting(session, _ACTIVE_VENUE_KEY) or "binance"


def set_active_venue(session: Session, venue: str) -> None:
    """Set the active trading venue."""
    set_setting(session, _ACTIVE_VENUE_KEY, venue)


def _venue_cred_key(venue: str, field: str) -> str:
    """The `Setting` key one venue credential field is stored under."""
    return f"venue:{venue}:{field}"


def set_venue_credentials(
    session: Session, venue: str, fields: dict[str, str]
) -> None:
    """Store a venue's credential fields, each encrypted at rest."""
    for field, value in fields.items():
        _put(session, _venue_cred_key(venue, field), value, is_secret=True)


def get_venue_credentials(session: Session, venue: str) -> dict[str, str]:
    """Decrypt and return every stored credential field for `venue`.

    Returns an empty dict when nothing is stored — callers check completeness
    against the venue's declared `credential_fields`.
    """
    prefix = f"venue:{venue}:"
    rows = session.exec(select(Setting).where(Setting.key.startswith(prefix))).all()
    return {row.key.removeprefix(prefix): decrypt(row.value) for row in rows}


def venue_credentials_configured(
    session: Session, venue: str, required: Iterable[str]
) -> bool:
    """Whether every `required` credential field for `venue` is stored.

    Checks for row presence only — values are not decrypted.
    """
    prefix = f"venue:{venue}:"
    stored = {
        row.key.removeprefix(prefix)
        for row in session.exec(
            select(Setting).where(Setting.key.startswith(prefix))
        ).all()
    }
    required = list(required)
    return bool(required) and all(field in stored for field in required)


# -- Binance credential shims --------------------------------------------------
# Binance credentials are `venue:binance:api_key` / `:api_secret`. These
# wrappers keep the existing call sites (executor router, recovery) stable.


def set_binance_keys(session: Session, api_key: str, api_secret: str) -> None:
    """Store the Binance API credentials, encrypted at rest."""
    set_venue_credentials(
        session, "binance", {"api_key": api_key, "api_secret": api_secret}
    )


def binance_keys_configured(session: Session) -> bool:
    """Whether both Binance credentials are stored (without decrypting them)."""
    return venue_credentials_configured(
        session, "binance", ("api_key", "api_secret")
    )


def get_binance_keys(session: Session) -> tuple[str, str] | None:
    """Decrypt and return `(api_key, api_secret)`, or None if unset."""
    creds = get_venue_credentials(session, "binance")
    if "api_key" in creds and "api_secret" in creds:
        return creds["api_key"], creds["api_secret"]
    return None


def get_ai_settings(session: Session) -> dict[str, str]:
    """The AI provider, model and base URL — the API key is excluded."""
    return {
        "provider": get_setting(session, _AI_PROVIDER) or "claude",
        "model": get_setting(session, _AI_MODEL) or "",
        "base_url": get_setting(session, _AI_BASE_URL) or "",
    }


def ai_key_configured(session: Session) -> bool:
    """Whether an AI API key is stored (without decrypting it)."""
    return _get(session, _AI_API_KEY) is not None


def get_ai_api_key(session: Session) -> str:
    """The decrypted AI API key, or an empty string if unset."""
    row = _get(session, _AI_API_KEY)
    return decrypt(row.value) if row is not None else ""


def set_ai_settings(
    session: Session,
    *,
    provider: str,
    model: str,
    base_url: str,
    api_key: str | None = None,
) -> None:
    """Store the AI provider config. The key is updated only when supplied."""
    set_setting(session, _AI_PROVIDER, provider)
    set_setting(session, _AI_MODEL, model)
    set_setting(session, _AI_BASE_URL, base_url)
    if api_key:
        _put(session, _AI_API_KEY, api_key, is_secret=True)


def get_ai_spend_cap(session: Session) -> Decimal:
    """The daily LLM spend cap in USD — `0` means unlimited (the default)."""
    val = get_setting(session, _AI_SPEND_CAP)
    return Decimal(val) if val else Decimal(0)


def set_ai_spend_cap(session: Session, cap: Decimal) -> None:
    """Set the daily LLM spend cap in USD (`0` disables the cap)."""
    set_setting(session, _AI_SPEND_CAP, str(cap))


# -- risk limits ----------------------------------------------------------------
# Runtime-editable risk controls. Each getter takes a `default` so callers can
# supply the env fallback; `_decimal_setting` returns `default` only when the
# key is unset — an explicitly-stored `"0"` is returned as `Decimal(0)`.


def get_risk_stop_loss_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Stop-loss as a percent of a position's entry value (0 = disabled)."""
    return _decimal_setting(session, _RISK_STOP_LOSS, default)


def set_risk_stop_loss_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_STOP_LOSS, str(pct))


def get_risk_take_profit_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Take-profit as a percent of a position's entry value (0 = disabled)."""
    return _decimal_setting(session, _RISK_TAKE_PROFIT, default)


def set_risk_take_profit_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_TAKE_PROFIT, str(pct))


def get_risk_max_drawdown_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Kill-switch drawdown limit as a percent from the equity peak (0 = disabled)."""
    return _decimal_setting(session, _RISK_MAX_DRAWDOWN, default)


def set_risk_max_drawdown_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_MAX_DRAWDOWN, str(pct))


def get_risk_daily_loss_limit(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Kill-switch daily realized-loss limit in quote currency (0 = disabled)."""
    return _decimal_setting(session, _RISK_DAILY_LOSS, default)


def set_risk_daily_loss_limit(session: Session, amount: Decimal) -> None:
    set_setting(session, _RISK_DAILY_LOSS, str(amount))


def get_risk_max_position_notional(
    session: Session, default: Decimal = Decimal(0)
) -> Decimal:
    """Per-order notional cap in quote currency (0 = disabled)."""
    return _decimal_setting(session, _RISK_MAX_NOTIONAL, default)


def set_risk_max_position_notional(session: Session, amount: Decimal) -> None:
    set_setting(session, _RISK_MAX_NOTIONAL, str(amount))


# -- per-provider LLM credentials ---------------------------------------------
# Each LLM provider stores its own credentials, so a Claude strategy and a
# local-Ollama strategy can run side by side. Keys: `llm:{provider}:api_key`
# (encrypted) and `llm:{provider}:base_url` (plain — for Ollama / compatible
# endpoints). Ollama is local and needs no key.

#: LLM providers an AI strategy can be pointed at.
LLM_PROVIDERS: tuple[str, ...] = ("claude", "openai", "gemini", "ollama")


def set_llm_credentials(
    session: Session,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Store one provider's credentials. Each field updates only when given."""
    if api_key:
        _put(session, f"llm:{provider}:api_key", api_key, is_secret=True)
    if base_url is not None:
        set_setting(session, f"llm:{provider}:base_url", base_url)


def get_llm_credentials(session: Session, provider: str) -> dict[str, str]:
    """The decrypted `api_key` and `base_url` for a provider (blank if unset)."""
    key_row = _get(session, f"llm:{provider}:api_key")
    return {
        "api_key": decrypt(key_row.value) if key_row is not None else "",
        "base_url": get_setting(session, f"llm:{provider}:base_url") or "",
    }


def llm_provider_configured(session: Session, provider: str) -> bool:
    """Whether a provider is usable — Ollama always is; others need a key."""
    if provider == "ollama":
        return True
    return _get(session, f"llm:{provider}:api_key") is not None


def get_strategy_ai_config(session: Session, strategy: str) -> dict[str, str]:
    """An AI strategy's provider + model, falling back to the global setting."""
    ai = get_ai_settings(session)
    return {
        "provider": get_setting(session, f"ai:{strategy}:provider") or ai["provider"],
        "model": get_setting(session, f"ai:{strategy}:model") or ai["model"],
    }


def set_strategy_ai_config(
    session: Session, strategy: str, *, provider: str, model: str
) -> None:
    """Pin an AI strategy to a specific provider + model."""
    set_setting(session, f"ai:{strategy}:provider", provider)
    set_setting(session, f"ai:{strategy}:model", model)


# -- AI action mode (notify vs auto-execute) ----------------------------------
# The global default is `notify`: an AI decision is surfaced for operator
# confirmation rather than executed. A strategy may override the global mode.


def _normalise_mode(value: str | None, default: str = "notify") -> str:
    """Coerce a stored value to a known mode, defaulting safely to `notify`."""
    return value if value in AI_ACTION_MODES else default


def get_ai_action_mode(session: Session) -> str:
    """The global AI action mode — `notify` (default) or `auto`."""
    return _normalise_mode(get_setting(session, _AI_ACTION_MODE))


def set_ai_action_mode(session: Session, mode: str) -> None:
    """Set the global AI action mode."""
    set_setting(session, _AI_ACTION_MODE, _normalise_mode(mode))


def get_strategy_action_mode(session: Session, strategy: str) -> str:
    """An AI strategy's action mode, falling back to the global default."""
    override = get_setting(session, f"ai:{strategy}:action_mode")
    return _normalise_mode(override, default=get_ai_action_mode(session))


def set_strategy_action_mode(session: Session, strategy: str, mode: str) -> None:
    """Pin an AI strategy to a specific action mode."""
    set_setting(session, f"ai:{strategy}:action_mode", _normalise_mode(mode))


# -- research reports -----------------------------------------------------------
# Scheduled research reports: which symbols are watched, how often a report is
# written, and which LLM writes the narrative sections (falls back to the
# global AI setting when unset).

_RESEARCH_SYMBOLS = "research_symbols"
_RESEARCH_INTERVAL = "research_interval_hours"
_NEWS_INTERVAL = "news_interval_hours"

#: Symbols researched when the operator has not configured a list.
DEFAULT_RESEARCH_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")


def get_research_symbols(session: Session) -> list[str]:
    """The watched symbols a research cycle reports on."""
    raw = get_setting(session, _RESEARCH_SYMBOLS)
    if not raw:
        return list(DEFAULT_RESEARCH_SYMBOLS)
    try:
        items = json.loads(raw)
        symbols = [str(s).upper() for s in items if str(s).strip()]
        return symbols or list(DEFAULT_RESEARCH_SYMBOLS)
    except (json.JSONDecodeError, TypeError):
        return list(DEFAULT_RESEARCH_SYMBOLS)


def set_research_symbols(session: Session, symbols: list[str]) -> None:
    """Set the watched research symbols."""
    set_setting(session, _RESEARCH_SYMBOLS, json.dumps([s.upper() for s in symbols]))


def get_research_interval_hours(session: Session) -> int:
    """Hours between scheduled research cycles (default 12, minimum 1)."""
    raw = get_setting(session, _RESEARCH_INTERVAL)
    try:
        return max(1, int(raw)) if raw else 12
    except ValueError:
        return 12


def set_research_interval_hours(session: Session, hours: int) -> None:
    """Set the research cycle interval in hours."""
    set_setting(session, _RESEARCH_INTERVAL, str(max(1, hours)))


def get_research_writer(session: Session) -> dict[str, str]:
    """The report-writer LLM `{provider, model}` — defaults to the AI setting."""
    ai = get_ai_settings(session)
    return {
        "provider": get_setting(session, "research:writer:provider") or ai["provider"],
        "model": get_setting(session, "research:writer:model") or ai["model"],
    }


def set_research_writer(session: Session, *, provider: str, model: str) -> None:
    """Pin the report writer to a specific provider + model."""
    set_setting(session, "research:writer:provider", provider)
    set_setting(session, "research:writer:model", model)


def get_news_interval_hours(session: Session) -> int | None:
    """Hours between news refreshes — None keeps the default daily schedule."""
    raw = get_setting(session, _NEWS_INTERVAL)
    try:
        return max(1, int(raw)) if raw else None
    except ValueError:
        return None


def set_news_interval_hours(session: Session, hours: int | None) -> None:
    """Set the news refresh interval (None/0 restores the daily schedule)."""
    set_setting(session, _NEWS_INTERVAL, str(hours) if hours else "")


# -- polymarket -------------------------------------------------------------------
# Prediction-market discovery and AI bet analysis: how often the market
# catalogue refreshes, how often the screener analyses bets, and the edge /
# confidence bar a suggestion must clear. Deliberately slow cadences —
# prediction markets move on events and news, not ticks.

_POLYMARKET_REFRESH = "polymarket_refresh_hours"
_POLYMARKET_RESEARCH = "polymarket_research_hours"
_POLYMARKET_EDGE = "polymarket_edge_threshold"
_POLYMARKET_CONFIDENCE = "polymarket_min_confidence"
_POLYMARKET_SCREEN_TOP = "polymarket_screen_top"
_POLYMARKET_STAKE = "polymarket_stake"


def _int_setting(session: Session, key: str, default: int, *, minimum: int = 0) -> int:
    raw = get_setting(session, key)
    try:
        return max(minimum, int(raw)) if raw else default
    except ValueError:
        return default


def _decimal_setting(session: Session, key: str, default: Decimal) -> Decimal:
    raw = get_setting(session, key)
    try:
        return Decimal(raw) if raw else default
    except InvalidOperation:
        return default


def get_polymarket_refresh_hours(session: Session) -> int:
    """Hours between market-catalogue refreshes (default 6, minimum 1)."""
    return _int_setting(session, _POLYMARKET_REFRESH, 6, minimum=1)


def set_polymarket_refresh_hours(session: Session, hours: int) -> None:
    set_setting(session, _POLYMARKET_REFRESH, str(max(1, hours)))


def get_polymarket_research_hours(session: Session) -> int:
    """Hours between AI bet-screening cycles (default 6, minimum 1)."""
    return _int_setting(session, _POLYMARKET_RESEARCH, 6, minimum=1)


def set_polymarket_research_hours(session: Session, hours: int) -> None:
    set_setting(session, _POLYMARKET_RESEARCH, str(max(1, hours)))


def get_polymarket_edge_threshold(session: Session) -> Decimal:
    """Minimum |estimated probability − market price| to suggest a bet."""
    return _decimal_setting(session, _POLYMARKET_EDGE, Decimal("0.05"))


def set_polymarket_edge_threshold(session: Session, threshold: Decimal) -> None:
    set_setting(session, _POLYMARKET_EDGE, str(threshold))


def get_polymarket_min_confidence(session: Session) -> Decimal:
    """Minimum model confidence for a suggestion (default 0.6)."""
    return _decimal_setting(session, _POLYMARKET_CONFIDENCE, Decimal("0.6"))


def set_polymarket_min_confidence(session: Session, confidence: Decimal) -> None:
    set_setting(session, _POLYMARKET_CONFIDENCE, str(confidence))


def get_polymarket_screen_top(session: Session) -> int:
    """How many top-volume markets the screener analyses besides the watchlist."""
    return _int_setting(session, _POLYMARKET_SCREEN_TOP, 10)


def set_polymarket_screen_top(session: Session, count: int) -> None:
    set_setting(session, _POLYMARKET_SCREEN_TOP, str(max(0, count)))


def get_polymarket_stake(session: Session) -> Decimal:
    """Suggested stake per screener signal, in USDC (default 100)."""
    return _decimal_setting(session, _POLYMARKET_STAKE, Decimal("100"))


def set_polymarket_stake(session: Session, stake: Decimal) -> None:
    set_setting(session, _POLYMARKET_STAKE, str(stake))


# -- feed latency ---------------------------------------------------------------

_LATENCY_WARN_MS = "latency_warn_ms"


def get_latency_warn_ms(session: Session) -> int:
    """Feed latency above this (ms) marks the feed degraded (default 2000)."""
    raw = get_setting(session, _LATENCY_WARN_MS)
    try:
        return max(100, int(raw)) if raw else 2000
    except ValueError:
        return 2000


def set_latency_warn_ms(session: Session, warn_ms: int) -> None:
    """Set the degraded-feed warning threshold in milliseconds."""
    set_setting(session, _LATENCY_WARN_MS, str(max(100, warn_ms)))

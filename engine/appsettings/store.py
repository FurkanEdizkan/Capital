"""Runtime-settings store — trading mode and encrypted venue credentials.

`config.Settings` holds static process config; this module holds settings an
operator changes at runtime through the Settings page, persisted in the DB.

Venue credentials are stored per-venue, one encrypted row per field, keyed
`venue:{venue}:{field}` — so each venue declares its own credential shape
(Binance/Alpaca: api_key+api_secret; Polymarket: wallet key+address).
"""

from collections.abc import Iterable
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

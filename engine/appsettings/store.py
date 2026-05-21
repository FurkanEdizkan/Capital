"""Runtime-settings store — trading mode and encrypted Binance credentials.

`config.Settings` holds static process config; this module holds settings an
operator changes at runtime through the Settings page, persisted in the DB.
"""

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
_BINANCE_KEY = "binance_api_key"
_BINANCE_SECRET = "binance_api_secret"


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


def set_binance_keys(session: Session, api_key: str, api_secret: str) -> None:
    """Store the Binance API credentials, encrypted at rest."""
    _put(session, _BINANCE_KEY, api_key, is_secret=True)
    _put(session, _BINANCE_SECRET, api_secret, is_secret=True)


def binance_keys_configured(session: Session) -> bool:
    """Whether both Binance credentials are stored (without decrypting them)."""
    return _get(session, _BINANCE_KEY) is not None and _get(session, _BINANCE_SECRET) is not None


def get_binance_keys(session: Session) -> tuple[str, str] | None:
    """Decrypt and return `(api_key, api_secret)`, or None if unset."""
    key = _get(session, _BINANCE_KEY)
    secret = _get(session, _BINANCE_SECRET)
    if key is None or secret is None:
        return None
    return decrypt(key.value), decrypt(secret.value)

"""Tests for runtime settings — encryption and the settings store."""

import pytest
from sqlmodel import Session, select

from appsettings.crypto import decrypt, encrypt
from appsettings.models import Setting
from appsettings.store import (
    TradingMode,
    binance_keys_configured,
    get_binance_keys,
    get_mode,
    set_binance_keys,
    set_mode,
)


def test_encrypt_decrypt_round_trip() -> None:
    assert decrypt(encrypt("my-secret-value")) == "my-secret-value"


def test_ciphertext_does_not_leak_plaintext() -> None:
    assert "hunter2" not in encrypt("hunter2")


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        decrypt("not-a-valid-token")


def test_mode_defaults_to_sim(session: Session) -> None:
    assert get_mode(session) is TradingMode.sim


def test_set_and_get_mode(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    assert get_mode(session) is TradingMode.testnet
    set_mode(session, TradingMode.live)
    assert get_mode(session) is TradingMode.live


def test_binance_keys_round_trip(session: Session) -> None:
    assert binance_keys_configured(session) is False
    set_binance_keys(session, "API-KEY-123", "API-SECRET-456")
    assert binance_keys_configured(session) is True
    assert get_binance_keys(session) == ("API-KEY-123", "API-SECRET-456")


def test_binance_keys_are_stored_encrypted(session: Session) -> None:
    set_binance_keys(session, "PLAINKEY", "PLAINSECRET")
    for row in session.exec(select(Setting)).all():
        assert row.is_secret
        assert "PLAINKEY" not in row.value
        assert "PLAINSECRET" not in row.value

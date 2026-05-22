"""Tests for runtime settings — encryption and the settings store."""

import pytest
from sqlmodel import Session, select

from appsettings.crypto import decrypt, encrypt
from appsettings.models import Setting
from appsettings.store import (
    TradingMode,
    binance_keys_configured,
    get_binance_keys,
    get_llm_credentials,
    get_mode,
    get_strategy_ai_config,
    get_venue_credentials,
    llm_provider_configured,
    set_binance_keys,
    set_llm_credentials,
    set_mode,
    set_strategy_ai_config,
    set_venue_credentials,
    venue_credentials_configured,
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


def test_venue_credentials_round_trip(session: Session) -> None:
    set_venue_credentials(
        session, "alpaca", {"api_key": "AK", "api_secret": "AS"}
    )
    assert get_venue_credentials(session, "alpaca") == {
        "api_key": "AK",
        "api_secret": "AS",
    }


def test_venue_credentials_are_isolated_per_venue(session: Session) -> None:
    set_venue_credentials(session, "alpaca", {"api_key": "AK", "api_secret": "AS"})
    set_venue_credentials(
        session, "polymarket", {"wallet_private_key": "PK", "wallet_address": "0xAB"}
    )
    assert get_venue_credentials(session, "alpaca") == {
        "api_key": "AK",
        "api_secret": "AS",
    }
    assert get_venue_credentials(session, "polymarket")["wallet_address"] == "0xAB"


def test_venue_credentials_stored_encrypted(session: Session) -> None:
    set_venue_credentials(session, "alpaca", {"api_key": "PLAINAK", "api_secret": "X"})
    for row in session.exec(select(Setting)).all():
        assert row.is_secret
        assert "PLAINAK" not in row.value


def test_venue_credentials_configured_checks_all_required(session: Session) -> None:
    required = ("api_key", "api_secret")
    assert venue_credentials_configured(session, "alpaca", required) is False
    set_venue_credentials(session, "alpaca", {"api_key": "AK"})  # partial
    assert venue_credentials_configured(session, "alpaca", required) is False
    set_venue_credentials(session, "alpaca", {"api_secret": "AS"})
    assert venue_credentials_configured(session, "alpaca", required) is True


def test_binance_wrappers_use_the_venue_namespace(session: Session) -> None:
    # The binance shims write into the generic venue:* credential store.
    set_binance_keys(session, "BK", "BS")
    assert get_venue_credentials(session, "binance") == {
        "api_key": "BK",
        "api_secret": "BS",
    }


def test_llm_credentials_round_trip(session: Session) -> None:
    set_llm_credentials(session, "openai", api_key="sk-123", base_url="https://x")
    creds = get_llm_credentials(session, "openai")
    assert creds == {"api_key": "sk-123", "base_url": "https://x"}


def test_llm_provider_configured(session: Session) -> None:
    # Ollama is local — always usable; others need a key.
    assert llm_provider_configured(session, "ollama") is True
    assert llm_provider_configured(session, "claude") is False
    set_llm_credentials(session, "claude", api_key="sk-claude")
    assert llm_provider_configured(session, "claude") is True


def test_llm_key_stored_encrypted(session: Session) -> None:
    set_llm_credentials(session, "gemini", api_key="PLAINGEMINI")
    for row in session.exec(select(Setting)).all():
        if row.key.endswith("api_key"):
            assert "PLAINGEMINI" not in row.value


def test_strategy_ai_config_falls_back_to_global(session: Session) -> None:
    # With nothing set, a strategy inherits the global AI provider default.
    cfg = get_strategy_ai_config(session, "AI BTC")
    assert cfg["provider"] == "claude"


def test_strategy_ai_config_round_trip(session: Session) -> None:
    set_strategy_ai_config(session, "AI BTC", provider="ollama", model="qwen2.5")
    cfg = get_strategy_ai_config(session, "AI BTC")
    assert cfg == {"provider": "ollama", "model": "qwen2.5"}

"""Tests for per-strategy AI provider resolution."""

from sqlmodel import Session

from ai.resolve import strategy_ai_settings
from appsettings.store import set_strategy_ai_config


def test_resolves_the_global_default(session: Session) -> None:
    # With no per-strategy config, an AI strategy inherits the global default.
    provider, _model = strategy_ai_settings(session, "AI Trader BTC")
    assert provider.name == "claude"


def test_resolves_a_per_strategy_ollama_model(session: Session) -> None:
    set_strategy_ai_config(
        session, "AI Trader BTC", provider="ollama", model="qwen2.5"
    )
    provider, model = strategy_ai_settings(session, "AI Trader BTC")
    # Ollama reports its own name (not "openai") so usage is costed as free.
    assert provider.name == "ollama"
    assert model == "qwen2.5"


def test_two_strategies_resolve_independently(session: Session) -> None:
    set_strategy_ai_config(session, "AI Trader BTC", provider="claude", model="c")
    set_strategy_ai_config(session, "AI Trader ETH", provider="ollama", model="qwen")
    btc, _ = strategy_ai_settings(session, "AI Trader BTC")
    eth, _ = strategy_ai_settings(session, "AI Trader ETH")
    assert btc.name == "claude"
    assert eth.name == "ollama"

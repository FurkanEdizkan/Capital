"""Tests for AI decision-prompt enrichment (news + connections context)."""

from decimal import Decimal

from ai.analyze import build_decision_prompt, build_market_prompt
from ai.providers.base import Completion, LLMProvider
from strategies.ai_strategy import AIStrategy
from tests.test_ai_strategy import _ctx, _flat


def test_build_decision_prompt_includes_news_and_connections() -> None:
    prompt = build_decision_prompt(
        symbol="BTCUSDT",
        closes=[Decimal("100"), Decimal("101")],
        position_side="flat",
        position_qty=Decimal("0"),
        allocation=Decimal("1000"),
        price=Decimal("101"),
        news=["Bitcoin ETF approved"],
        connections=["US Dollar", "Stablecoin"],
    )
    assert "Recent news for BTCUSDT" in prompt
    assert "Bitcoin ETF approved" in prompt
    assert "Known connections for BTCUSDT" in prompt
    assert "US Dollar" in prompt


def test_build_market_prompt_omits_empty_context() -> None:
    prompt = build_market_prompt(
        symbol="BTCUSDT",
        closes=[Decimal("100"), Decimal("101")],
        position_side="flat",
        position_qty=Decimal("0"),
        allocation=Decimal("1000"),
        price=Decimal("101"),
    )
    assert "Recent news" not in prompt
    assert "Known connections" not in prompt


class CapturingProvider(LLMProvider):
    """Records the prompt it was asked to complete."""

    name = "fake"

    def __init__(self) -> None:
        self.prompt = ""

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        self.prompt = prompt
        return Completion(
            text='{"action": "hold", "confidence": 0.5, "reasoning": "x"}',
            provider=self.name,
            model=model or "m",
            input_tokens=1,
            output_tokens=1,
        )


def test_context_providers_feed_the_prompt() -> None:
    provider = CapturingProvider()
    strat = AIStrategy("AI BTC", "BTCUSDT", provider=provider)
    strat.set_context_providers(
        news=lambda _s: ["Headline one"],
        connections=lambda _s: ["AI compute"],
    )
    strat.evaluate(_ctx(_flat()))
    assert "Headline one" in provider.prompt
    assert "AI compute" in provider.prompt

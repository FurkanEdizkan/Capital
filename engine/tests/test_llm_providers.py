"""Tests for the LLM provider adapters — hermetic, fake SDK clients."""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from ai.providers import ClaudeProvider, GeminiProvider, OpenAIProvider, get_provider
from ai.providers.base import DecisionAction, LLMError, parse_decision

_DECISION_JSON = '{"action": "buy", "confidence": 0.8, "reasoning": "clear uptrend"}'


class FakeClaude:
    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text, self._raises = text, raises
        self.messages = self

    def create(self, **_: Any) -> Any:
        if self._raises:
            raise RuntimeError("api unavailable")
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class FakeOpenAI:
    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text, self._raises = text, raises
        self.chat = self
        self.completions = self

    def create(self, **_: Any) -> Any:
        if self._raises:
            raise RuntimeError("api unavailable")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._text))]
        )


class FakeGemini:
    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text, self._raises = text, raises
        self.models = self

    def generate_content(self, **_: Any) -> Any:
        if self._raises:
            raise RuntimeError("api unavailable")
        return SimpleNamespace(text=self._text)


# --- parse_decision --------------------------------------------------------

def test_parse_decision_valid() -> None:
    decision = parse_decision(_DECISION_JSON)
    assert decision.action is DecisionAction.buy
    assert decision.confidence == Decimal("0.8")
    assert decision.reasoning == "clear uptrend"


def test_parse_decision_embedded_in_prose() -> None:
    text = f"Here is my analysis. {_DECISION_JSON} That is my call."
    assert parse_decision(text).action is DecisionAction.buy


def test_parse_decision_without_json_raises() -> None:
    with pytest.raises(LLMError):
        parse_decision("I think you should buy.")


def test_parse_decision_with_bad_action_raises() -> None:
    with pytest.raises(LLMError):
        parse_decision('{"action": "yolo", "confidence": 0.5}')


# --- adapters --------------------------------------------------------------

def test_claude_provider_completes_and_decides() -> None:
    provider = ClaudeProvider(client=FakeClaude(_DECISION_JSON))
    assert provider.complete("prompt") == _DECISION_JSON
    assert provider.decide("prompt").action is DecisionAction.buy


def test_openai_provider_completes_and_decides() -> None:
    provider = OpenAIProvider(client=FakeOpenAI(_DECISION_JSON))
    assert provider.decide("prompt").confidence == Decimal("0.8")


def test_gemini_provider_completes_and_decides() -> None:
    provider = GeminiProvider(client=FakeGemini(_DECISION_JSON))
    assert provider.decide("prompt").action is DecisionAction.buy


def test_adapter_wraps_sdk_errors() -> None:
    provider = ClaudeProvider(client=FakeClaude(raises=True))
    with pytest.raises(LLMError):
        provider.complete("prompt")


# --- get_provider ----------------------------------------------------------

def test_get_provider_resolves_adapters() -> None:
    assert isinstance(get_provider("claude"), ClaudeProvider)
    assert isinstance(get_provider("gemini"), GeminiProvider)
    # OpenAI-compatible names all map onto the OpenAI adapter.
    assert isinstance(get_provider("openai"), OpenAIProvider)
    assert isinstance(get_provider("deepseek"), OpenAIProvider)
    assert isinstance(get_provider("ollama"), OpenAIProvider)


def test_get_provider_rejects_unknown() -> None:
    with pytest.raises(LLMError):
        get_provider("not-a-provider")

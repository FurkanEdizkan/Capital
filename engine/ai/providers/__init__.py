"""LLM provider adapters — Claude, OpenAI-compatible, Gemini.

`get_provider` builds the configured adapter. OpenAI-compatible covers
OpenAI, Codex, DeepSeek and Ollama via their shared API shape — only the
base URL differs.
"""

from ai.providers.base import (
    Decision,
    DecisionAction,
    LLMError,
    LLMProvider,
    parse_decision,
)
from ai.providers.claude import ClaudeProvider
from ai.providers.gemini import GeminiProvider
from ai.providers.openai import OpenAIProvider

#: Provider names that map onto the OpenAI-compatible adapter.
_OPENAI_COMPATIBLE = {"openai", "codex", "deepseek", "ollama"}

__all__ = [
    "ClaudeProvider",
    "Decision",
    "DecisionAction",
    "GeminiProvider",
    "LLMError",
    "LLMProvider",
    "OpenAIProvider",
    "get_provider",
    "parse_decision",
]


def get_provider(
    name: str, *, api_key: str = "", base_url: str = ""
) -> LLMProvider:
    """Build the LLM provider adapter for `name`.

    Raises `LLMError` for an unknown provider name.
    """
    key = name.strip().lower()
    if key == "claude":
        return ClaudeProvider(api_key)
    if key in _OPENAI_COMPATIBLE:
        return OpenAIProvider(api_key, base_url=base_url)
    if key == "gemini":
        return GeminiProvider(api_key)
    raise LLMError(f"unknown LLM provider: {name!r}")

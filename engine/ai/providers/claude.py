"""Anthropic Claude LLM adapter."""

from typing import Any

from ai.providers.base import LLMError, LLMProvider


class ClaudeProvider(LLMProvider):
    """LLM provider backed by the Anthropic Claude API."""

    name = "claude"
    default_model = "claude-sonnet-4-6"

    def __init__(self, api_key: str = "", *, client: Any | None = None) -> None:
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        # The SDK is imported lazily — only when a real call is made — so the
        # engine never hard-depends on it at startup, and tests inject a fake.
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        try:
            response = self._get_client().messages.create(
                model=model or self.default_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:  # noqa: BLE001 — normalise SDK errors
            raise LLMError(f"Claude completion failed: {exc}") from exc

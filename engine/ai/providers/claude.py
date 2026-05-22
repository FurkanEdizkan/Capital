"""Anthropic Claude LLM adapter."""

from typing import Any

from ai.providers.base import Completion, LLMError, LLMProvider


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

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        resolved = model or self.default_model
        try:
            response = self._get_client().messages.create(
                model=resolved,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            usage = getattr(response, "usage", None)
            return Completion(
                text=response.content[0].text,
                provider=self.name,
                model=resolved,
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
            )
        except Exception as exc:  # noqa: BLE001 — normalise SDK errors
            raise LLMError(f"Claude completion failed: {exc}") from exc

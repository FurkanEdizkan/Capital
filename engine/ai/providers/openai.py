"""OpenAI-compatible LLM adapter.

Serves OpenAI itself and any OpenAI-compatible endpoint — Codex, DeepSeek and
Ollama — by pointing `base_url` at the relevant service.
"""

from typing import Any

from ai.providers.base import LLMError, LLMProvider


class OpenAIProvider(LLMProvider):
    """LLM provider backed by the OpenAI API (or any compatible endpoint)."""

    name = "openai"
    default_model = "gpt-4o"

    def __init__(
        self, api_key: str = "", *, base_url: str = "", client: Any | None = None
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            kwargs: dict[str, Any] = {"api_key": self._api_key or "not-required"}
            if self._base_url:  # Codex / DeepSeek / Ollama / self-hosted
                kwargs["base_url"] = self._base_url
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        try:
            response = self._get_client().chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 — normalise SDK errors
            raise LLMError(f"OpenAI completion failed: {exc}") from exc

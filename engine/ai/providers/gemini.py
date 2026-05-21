"""Google Gemini LLM adapter."""

from typing import Any

from ai.providers.base import LLMError, LLMProvider


class GeminiProvider(LLMProvider):
    """LLM provider backed by the Google Gemini API."""

    name = "gemini"
    default_model = "gemini-2.0-flash"

    def __init__(self, api_key: str = "", *, client: Any | None = None) -> None:
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        try:
            response = self._get_client().models.generate_content(
                model=model or self.default_model,
                contents=prompt,
            )
            return response.text or ""
        except Exception as exc:  # noqa: BLE001 — normalise SDK errors
            raise LLMError(f"Gemini completion failed: {exc}") from exc

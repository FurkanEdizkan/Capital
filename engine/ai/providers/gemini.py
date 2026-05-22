"""Google Gemini LLM adapter."""

from typing import Any

from ai.providers.base import Completion, LLMError, LLMProvider


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

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        resolved = model or self.default_model
        try:
            response = self._get_client().models.generate_content(
                model=resolved,
                contents=prompt,
            )
            usage = getattr(response, "usage_metadata", None)
            return Completion(
                text=response.text or "",
                provider=self.name,
                model=resolved,
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            )
        except Exception as exc:  # noqa: BLE001 — normalise SDK errors
            raise LLMError(f"Gemini completion failed: {exc}") from exc

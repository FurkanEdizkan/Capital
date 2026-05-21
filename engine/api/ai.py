"""AI API — the analyze-and-decide endpoint.

An operator (or an agent) submits a free-form task; the configured LLM
returns a structured `Decision`. Executing that decision is a separate,
risk- and role-gated step — this endpoint only advises.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ai.analyze import analyze
from ai.providers import LLMError, get_provider
from ai.providers.base import Decision, LLMProvider
from auth.deps import CurrentUser
from config import settings

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_llm_provider() -> LLMProvider:
    """The LLM provider built from configuration (overridable in tests)."""
    return get_provider(
        settings.ai_provider,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
    )


ProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


class AnalyzeRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


@router.post("/analyze", response_model=Decision)
def analyze_and_decide(
    body: AnalyzeRequest, _: CurrentUser, provider: ProviderDep
) -> Decision:
    """Run a free-form analyze-and-decide task through the configured LLM."""
    try:
        return analyze(provider, task=body.task, model=settings.ai_model or None)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"AI analysis failed: {exc}"
        ) from exc

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
from appsettings.store import get_ai_api_key, get_ai_settings
from auth.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_llm_provider(session: SessionDep) -> LLMProvider:
    """The LLM provider built from the stored AI settings (overridable)."""
    ai = get_ai_settings(session)
    return get_provider(
        ai["provider"],
        api_key=get_ai_api_key(session),
        base_url=ai["base_url"],
    )


ProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


class AnalyzeRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


@router.post("/analyze", response_model=Decision)
def analyze_and_decide(
    body: AnalyzeRequest,
    _: CurrentUser,
    session: SessionDep,
    provider: ProviderDep,
) -> Decision:
    """Run a free-form analyze-and-decide task through the configured LLM."""
    model = get_ai_settings(session)["model"] or None
    try:
        return analyze(provider, task=body.task, model=model)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"AI analysis failed: {exc}"
        ) from exc

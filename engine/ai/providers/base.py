"""LLMProvider — a provider-agnostic interface for LLM completions.

Each adapter wraps a vendor SDK behind `complete()`. `decide()` is shared: it
asks for a completion and parses a structured trading `Decision` out of it,
so AI strategies and the analyze-and-decide endpoint never depend on which
model is configured.
"""

import json
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, Field


class LLMError(Exception):
    """An LLM call failed or returned an unusable response."""


class DecisionAction(StrEnum):
    buy = "buy"
    sell = "sell"
    hold = "hold"


class Decision(BaseModel):
    """A structured trading decision parsed from an LLM response."""

    action: DecisionAction
    confidence: Decimal = Field(ge=0, le=1)
    reasoning: str = ""


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_decision(text: str) -> Decision:
    """Extract a `Decision` from an LLM's text response.

    The response must contain a JSON object with `action`, `confidence` and
    `reasoning`. Raises `LLMError` when none can be parsed.
    """
    match = _JSON_RE.search(text)
    if not match:
        raise LLMError(f"no JSON object in LLM response: {text[:120]!r}")
    try:
        raw = json.loads(match.group(0))
        return Decision(
            action=DecisionAction(str(raw["action"]).lower()),
            confidence=Decimal(str(raw.get("confidence", "0"))),
            reasoning=str(raw.get("reasoning", "")),
        )
    except (json.JSONDecodeError, KeyError, ValueError, InvalidOperation) as exc:
        raise LLMError(f"could not parse a decision from the response: {exc}") from exc


class LLMProvider(ABC):
    """Provider-agnostic LLM interface."""

    name: str = "base"
    default_model: str = ""

    @abstractmethod
    def complete(self, prompt: str, *, model: str | None = None) -> str:
        """Return the model's text completion for `prompt`.

        Raises `LLMError` on any provider failure.
        """

    def decide(self, prompt: str, *, model: str | None = None) -> Decision:
        """Ask for a completion and parse a structured trading `Decision`."""
        return parse_decision(self.complete(prompt, model=model))

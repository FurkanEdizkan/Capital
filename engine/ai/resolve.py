"""Resolve the LLM provider an AI strategy should use this tick.

Each AI strategy stores its own provider + model (falling back to the global
AI setting). Credentials are stored per provider, so a Claude strategy and a
local-Ollama strategy can run side by side. The engine calls this each tick
before evaluating an AI strategy.
"""

from sqlmodel import Session

from ai.providers import LLMProvider, get_provider
from appsettings.store import get_llm_credentials, get_strategy_ai_config


def strategy_ai_settings(
    session: Session, strategy: str
) -> tuple[LLMProvider, str | None]:
    """Build the `(provider, model)` for `strategy` from its stored config.

    Raises `LLMError` if the configured provider name is unknown.
    """
    cfg = get_strategy_ai_config(session, strategy)
    creds = get_llm_credentials(session, cfg["provider"])
    provider = get_provider(
        cfg["provider"], api_key=creds["api_key"], base_url=creds["base_url"]
    )
    return provider, (cfg["model"] or None)

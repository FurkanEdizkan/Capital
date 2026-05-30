"""Analyze-and-decide — prompt building and free-form AI decisions.

Shared by `AIStrategy` (which decides every tick) and the analyze-and-decide
API endpoint (a one-off task). Both end with a structured `Decision` that
still flows through the risk manager and capital allocator.
"""

from decimal import Decimal

from ai.providers.base import Completion, Decision, LLMProvider, parse_decision

_JSON_INSTRUCTION = (
    'Respond ONLY with a JSON object of the form '
    '{"action": "buy"|"sell"|"hold", "confidence": <0..1>, "reasoning": "<text>"}.'
)


def build_decision_prompt(
    *,
    symbol: str,
    closes: list[Decimal],
    position_side: str,
    position_qty: Decimal,
    allocation: Decimal,
    price: Decimal,
    news: list[str] | None = None,
    connections: list[str] | None = None,
    lookback: int = 30,
) -> str:
    """Compose the per-tick context pack and instruction for a decision.

    Folds in recent per-asset news headlines and the asset's known graph
    connections when supplied — they give the model context beyond price.
    """
    recent = ", ".join(str(c) for c in closes[-lookback:])
    parts = [
        f"You are a disciplined trading assistant for {symbol}.",
        f"Recent closing prices (oldest first): {recent}.",
        f"Current position: {position_side} {position_qty}.",
        f"Capital allocation: {allocation}. Latest price: {price}.",
    ]
    if news:
        headlines = "\n".join(f"- {h}" for h in news)
        parts.append(f"Recent news for {symbol}:\n{headlines}")
    if connections:
        parts.append(f"Known connections for {symbol}: {', '.join(connections)}.")
    parts.append(f"Decide whether to buy, sell or hold. {_JSON_INSTRUCTION}")
    return "\n".join(parts)


def build_market_prompt(
    *,
    symbol: str,
    closes: list[Decimal],
    position_side: str,
    position_qty: Decimal,
    allocation: Decimal,
    price: Decimal,
    lookback: int = 30,
) -> str:
    """Backwards-compatible price-only prompt — delegates with no extra context."""
    return build_decision_prompt(
        symbol=symbol,
        closes=closes,
        position_side=position_side,
        position_qty=position_qty,
        allocation=allocation,
        price=price,
        lookback=lookback,
    )


def analyze(
    provider: LLMProvider, *, task: str, model: str | None = None
) -> tuple[Decision, Completion]:
    """Run a free-form analyze-and-decide task through the LLM.

    Returns the structured `Decision` and the `Completion` (for usage/cost
    tracking); executing the decision remains a separate, risk- and role-gated
    step.
    """
    prompt = f"{task}\n\n{_JSON_INSTRUCTION}"
    completion = provider.complete(prompt, model=model)
    return parse_decision(completion.text), completion

"""Strategy read model — the single unit that projects a strategy into the
shape the API and dashboard show.

`read_strategy_state` is the one entrypoint: it gathers a strategy's identity,
lifecycle state, accounting summary and (for AI strategies) its configured LLM
into one `StrategyRead`. Keeping this here, rather than inline in the route
handlers, means the API layer only wires HTTP to it and the projection is
testable on its own.
"""

from decimal import Decimal

from pydantic import BaseModel
from sqlmodel import Session

from appsettings.store import get_strategy_ai_config
from strategies.base import BaseStrategy
from trading.accounting import strategy_summary
from trading.lifecycle import is_enabled


class StrategyRead(BaseModel):
    """A strategy's identity, lifecycle state and accounting summary."""

    name: str
    kind: str
    symbol: str
    market: str
    timeframe: str
    enabled: bool
    allocated: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    open_positions: int
    # The configured LLM provider + model — set only for AI strategies.
    ai_provider: str | None = None
    ai_model: str | None = None


def read_strategy_state(
    session: Session, strategy: BaseStrategy, marks: dict[str, Decimal]
) -> StrategyRead:
    """Project `strategy` into its read model.

    `session` and `strategy` are injected; `marks` ({symbol: price}) is the data
    used to value open positions. Returns one `StrategyRead` combining the
    accounting summary, lifecycle state and AI config.
    """
    summary = strategy_summary(session, strategy.name, marks)
    ai_provider: str | None = None
    ai_model: str | None = None
    if getattr(strategy, "kind", "") == "AI":
        cfg = get_strategy_ai_config(session, strategy.name)
        ai_provider, ai_model = cfg["provider"], cfg["model"]
    return StrategyRead(
        name=strategy.name,
        kind=strategy.kind,
        symbol=strategy.symbol,
        market=strategy.market.value,
        timeframe=strategy.timeframe,
        enabled=is_enabled(session, strategy.name),
        allocated=summary.allocated,
        realized_pnl=summary.realized_pnl,
        unrealized_pnl=summary.unrealized_pnl,
        fees=summary.fees,
        net_pnl=summary.net_pnl,
        open_positions=summary.open_positions,
        ai_provider=ai_provider,
        ai_model=ai_model,
    )

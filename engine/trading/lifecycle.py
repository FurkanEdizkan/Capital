"""Strategy lifecycle — enabled/disabled state and safe deletion.

A strategy's lifecycle state lives on its `StrategyAllocation` row:

- **enabled** (default) — the engine ticks it for new entries.
- **disabled** — the engine skips it; its open positions are kept and must be
  closed manually. New entries stop, but nothing is orphaned.
- **deleted** — only permitted once the strategy is flat, so a position is
  never left without a managing strategy.
"""

from sqlmodel import Session, select

from trading.models import StrategyAllocation
from trading.portfolio import list_positions


class StrategyLifecycleError(Exception):
    """A lifecycle action was rejected (e.g. deleting a strategy still in a trade)."""


def _row(session: Session, strategy: str) -> StrategyAllocation | None:
    return session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == strategy)
    ).first()


def is_enabled(session: Session, strategy: str) -> bool:
    """Whether the engine should tick `strategy` for new entries.

    A strategy with no config row yet is treated as enabled — that is the
    default for a freshly registered built-in before its row is seeded.
    """
    row = _row(session, strategy)
    return True if row is None else row.enabled


def set_enabled(session: Session, strategy: str, enabled: bool) -> StrategyAllocation:
    """Enable or disable `strategy`, creating its config row if needed."""
    row = _row(session, strategy)
    if row is None:
        row = StrategyAllocation(strategy=strategy, enabled=enabled)
    else:
        row.enabled = enabled
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_strategy(session: Session, strategy: str) -> None:
    """Remove a strategy's config and (flat) position rows.

    Blocked with `StrategyLifecycleError` while the strategy holds an open
    position — flatten it first so the position is never orphaned.
    """
    open_positions = list_positions(session, strategy=strategy, open_only=True)
    if open_positions:
        raise StrategyLifecycleError(
            f"cannot delete strategy {strategy!r} — it has "
            f"{len(open_positions)} open position(s); close them first"
        )
    for pos in list_positions(session, strategy=strategy):
        session.delete(pos)
    row = _row(session, strategy)
    if row is not None:
        session.delete(row)
    session.commit()

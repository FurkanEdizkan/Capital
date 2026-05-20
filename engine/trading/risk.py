"""Risk manager — order sizing caps, stop-loss / take-profit, kill switch.

The risk manager is the last gate before an order reaches an executor. It
enforces global limits that sit *above* per-strategy allocation:

- **Order sizing** — caps the notional value of any single order.
- **Stop-loss / take-profit** — force-closes a position whose unrealized PnL
  breaches a configured percentage of its entry value.
- **Kill switch** — halts new exposure when the day's realized loss or the
  equity drawdown from peak exceeds a limit. Closing trades stay allowed.

Every limit defaults to 0, meaning *disabled*, so risk control is strictly
opt-in (configured via `CAPITAL_RISK_*` settings).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session, select

from config import Settings
from trading.executors.base import Order
from trading.models import EquitySnapshot, FillSide, Position, PositionSide, Trade
from trading.portfolio import unrealized_pnl


def _signed_qty(pos: Position) -> Decimal:
    """Position size as a signed number — long positive, short negative."""
    if pos.side == PositionSide.long.value:
        return pos.qty
    if pos.side == PositionSide.short.value:
        return -pos.qty
    return Decimal(0)


@dataclass
class RiskManager:
    """Global risk limits applied to every order before execution."""

    max_position_notional: Decimal = Decimal(0)
    stop_loss_pct: Decimal = Decimal(0)
    take_profit_pct: Decimal = Decimal(0)
    daily_loss_limit: Decimal = Decimal(0)
    max_drawdown_pct: Decimal = Decimal(0)

    @classmethod
    def from_settings(cls, settings: Settings) -> "RiskManager":
        return cls(
            max_position_notional=settings.risk_max_position_notional,
            stop_loss_pct=settings.risk_stop_loss_pct,
            take_profit_pct=settings.risk_take_profit_pct,
            daily_loss_limit=settings.risk_daily_loss_limit,
            max_drawdown_pct=settings.risk_max_drawdown_pct,
        )

    # -- stop-loss / take-profit ---------------------------------------------

    def stop_order(self, position: Position, mark_price: Decimal) -> Order | None:
        """Return a full-close order if `position` breached its SL/TP, else None."""
        if position.side == PositionSide.flat.value or position.qty <= 0:
            return None
        basis = position.entry_price * position.qty
        if basis <= 0:
            return None

        pnl_pct = unrealized_pnl(position, Decimal(mark_price)) / basis * Decimal(100)
        hit_sl = self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct
        hit_tp = self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct
        if not (hit_sl or hit_tp):
            return None

        closing_side = (
            FillSide.sell if position.side == PositionSide.long.value else FillSide.buy
        )
        return Order(
            strategy=position.strategy,
            market=position.market,
            symbol=position.symbol,
            side=closing_side,
            quantity=position.qty,
        )

    # -- order sizing --------------------------------------------------------

    def cap_order_size(self, order: Order, price: Decimal) -> Order | None:
        """Clip an order so its notional value stays within the size limit."""
        if self.max_position_notional <= 0:
            return order  # sizing cap disabled
        price = Decimal(price)
        if price <= 0:
            return None
        max_qty = self.max_position_notional / price
        if order.quantity <= max_qty:
            return order
        return order.model_copy(update={"quantity": max_qty})

    # -- kill switch ---------------------------------------------------------

    def daily_realized_loss(self, session: Session) -> Decimal:
        """Net realized PnL (after fees) for trades executed today, UTC.

        Returns a signed number — negative means a loss.
        """
        today = datetime.now(UTC).date()
        start = datetime(today.year, today.month, today.day)
        trades = session.exec(select(Trade).where(Trade.executed_at >= start)).all()
        return sum((t.realized_pnl - t.fee for t in trades), Decimal(0))

    def equity_drawdown_pct(self, session: Session) -> Decimal:
        """Drawdown of the latest equity from its historical peak, percent."""
        snaps = session.exec(
            select(EquitySnapshot).order_by(EquitySnapshot.ts)  # type: ignore[arg-type]
        ).all()
        if not snaps:
            return Decimal(0)
        peak = max(s.equity for s in snaps)
        if peak <= 0:
            return Decimal(0)
        return max((peak - snaps[-1].equity) / peak * Decimal(100), Decimal(0))

    def kill_switch_tripped(self, session: Session) -> str | None:
        """Return a human-readable reason if trading is halted, else None."""
        if self.daily_loss_limit > 0:
            loss = self.daily_realized_loss(session)
            if loss <= -self.daily_loss_limit:
                return f"daily loss limit hit ({loss})"
        if self.max_drawdown_pct > 0:
            drawdown = self.equity_drawdown_pct(session)
            if drawdown >= self.max_drawdown_pct:
                return f"max drawdown hit ({drawdown:.2f}%)"
        return None

    # -- the gate ------------------------------------------------------------

    def review(
        self, session: Session, order: Order, position: Position, price: Decimal
    ) -> Order | None:
        """Apply the sizing cap and kill switch to a strategy order.

        Returns the order (possibly resized), or `None` if it is blocked. The
        kill switch only blocks orders that *increase* exposure — closing or
        reducing a position is always allowed so risk can be wound down.
        """
        sized = self.cap_order_size(order, price)
        if sized is None:
            return None
        if self._increases_exposure(sized, position) and self.kill_switch_tripped(session):
            return None
        return sized

    @staticmethod
    def _increases_exposure(order: Order, position: Position) -> bool:
        signed = _signed_qty(position)
        delta = order.quantity if order.side is FillSide.buy else -order.quantity
        return abs(signed + delta) > abs(signed)

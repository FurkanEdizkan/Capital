"""PredictionAIStrategy — trades Polymarket outcome tokens on AI-found edge.

A prediction market is not a chart to scalp: its price *is* a probability,
and it moves on events and news. So instead of the per-tick price prompt the
classic `AIStrategy` uses, this strategy reads the platform's stored AI bet
analyses (`polymarket.analysis`) — the LLM's probability estimate for the
market against its price — re-analysing at a slow, configurable cadence.

Decision rule per tick: enter when the analysis shows an edge on this token
at or above `edge_threshold` with confidence at or above `min_confidence`;
exit when the edge is gone. Orders still flow through the engine's
allocation, risk and action-mode (notify/auto) machinery, and the LLM spend
counts against the daily cap like every other AI call.

The strategy's symbol is one outcome token id (YES or NO); its venue is
always Polymarket.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, or_, select

from ai.providers.base import Decision, DecisionAction, LLMError
from exchange.client import Market
from polymarket.analysis import analyze_market, latest_analysis
from polymarket.models import MarketAnalysis, MarketStatus, PredictionMarket
from strategies.ai_strategy import AIStrategy
from strategies.base import StrategyContext
from trading.executors.base import Order
from trading.models import FillSide, PositionSide

log = logging.getLogger("capital.strategies.prediction_ai")


class PredictionAIStrategy(AIStrategy):
    """AI edge-trading on one Polymarket outcome token (long-only)."""

    kind = "Prediction AI"
    venue = "polymarket"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        edge_threshold: Decimal = Decimal("0.05"),
        min_confidence: Decimal = Decimal("0.6"),
        reanalyze_hours: int = 6,
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        self._edge_threshold = Decimal(edge_threshold)
        self._min_confidence = Decimal(min_confidence)
        self._reanalyze_hours = int(reanalyze_hours)
        # The tick's database session — analyses live in the database, so the
        # engine binds its session before each evaluate().
        self._session: Session | None = None

    def bind(self, session: Session) -> None:
        """Give the strategy the tick's session for analysis lookups."""
        self._session = session

    def _market(self, session: Session) -> PredictionMarket | None:
        """The catalogue market this strategy's outcome token belongs to."""
        return session.exec(
            select(PredictionMarket).where(
                or_(
                    PredictionMarket.yes_token_id == self.symbol,
                    PredictionMarket.no_token_id == self.symbol,
                )
            )
        ).first()

    def _fresh_analysis(
        self, session: Session, market: PredictionMarket
    ) -> MarketAnalysis | None:
        """The latest analysis, re-running the AI when it has gone stale.

        The inline `analyze_market` call records its own LLM usage, so
        `last_usage` stays None — the engine must not double-count it.
        """
        analysis = latest_analysis(session, market.condition_id)
        stale_after = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            hours=self._reanalyze_hours
        )
        if analysis is not None and analysis.created_at >= stale_after:
            return analysis
        if self._provider is None:
            return analysis  # no model configured — trade on what exists
        try:
            return analyze_market(
                session, market, provider=self._provider, model=self._model
            )
        except (LLMError, ValueError):
            log.warning(
                "prediction strategy %r — analysis failed, using last known",
                self.name,
                exc_info=True,
            )
            return analysis

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        self.last_usage = None
        self.last_decision = None
        session = self._session
        if session is None or ctx.price <= 0:
            return None
        market = self._market(session)
        if market is None:
            log.warning(
                "prediction strategy %r — token %s not in the market catalogue",
                self.name,
                self.symbol,
            )
            return None
        is_long = ctx.position.side == PositionSide.long.value
        if market.status != MarketStatus.active:
            # Closed/resolved markets are not tradeable; the resolution sync
            # settles any held tokens at 1/0.
            return None
        analysis = self._fresh_analysis(session, market)
        if analysis is None:
            return None
        # The stored edge is for YES; this token's edge mirrors for NO.
        is_yes = self.symbol == market.yes_token_id
        token_edge = analysis.edge if is_yes else -analysis.edge

        if (
            not is_long
            and token_edge >= self._edge_threshold
            and analysis.confidence >= self._min_confidence
            and ctx.allocation > 0
        ):
            self.last_decision = Decision(
                action=DecisionAction.buy,
                confidence=analysis.confidence,
                reasoning=(
                    f"{market.question} — edge {token_edge} on "
                    f"{'YES' if is_yes else 'NO'} (est P(YES) "
                    f"{analysis.est_probability} vs market {analysis.market_price}). "
                    f"{analysis.reasoning}"
                )[:2000],
            )
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,
            )
        if is_long and token_edge <= 0:
            self.last_decision = Decision(
                action=DecisionAction.sell,
                confidence=analysis.confidence,
                reasoning=(
                    f"{market.question} — edge gone on "
                    f"{'YES' if is_yes else 'NO'} ({token_edge}); exiting."
                ),
            )
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.sell,
                quantity=ctx.position.qty,
            )
        return None

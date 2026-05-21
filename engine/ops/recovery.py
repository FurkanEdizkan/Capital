"""Boot state recovery — reconcile open positions with Binance on startup.

After a restart the engine's sub-ledger may disagree with the exchange — an
order filled while the process was down, or a crash between placing and
recording one. On boot the engine reconciles and surfaces any drift so the
operator is not trading on stale state. Recovery never blocks startup.
"""

import logging

from binance.client import Client
from sqlmodel import Session

from appsettings.store import TradingMode, get_binance_keys, get_mode
from exchange.client import BinanceClient
from trading.reconcile import PositionDiscrepancy, reconcile_with_binance

log = logging.getLogger("capital.ops.recovery")


def recover_on_boot(
    session: Session, *, client: BinanceClient | None = None
) -> list[PositionDiscrepancy]:
    """Reconcile the engine sub-ledger against Binance positions at startup.

    In Sim mode there is nothing to reconcile. In Testnet/Live, compares the
    sub-ledger to Binance and logs any drift. Never raises — a reconciliation
    failure must not stop the engine from starting.
    """
    mode = get_mode(session)
    if mode is TradingMode.sim:
        log.info("boot recovery: sim mode — nothing to reconcile")
        return []

    if client is None:
        keys = get_binance_keys(session)
        if keys is None:
            log.warning("boot recovery: %s mode but Binance keys not configured", mode)
            return []
        api_key, api_secret = keys
        client = BinanceClient(
            Client(api_key, api_secret, testnet=mode is TradingMode.testnet)
        )

    try:
        discrepancies = reconcile_with_binance(session, client)
    except Exception:  # noqa: BLE001 — recovery must not block startup
        log.exception("boot recovery: reconciliation failed")
        return []

    if discrepancies:
        for d in discrepancies:
            log.warning(
                "boot recovery: position drift %s %s — engine %s, exchange %s",
                d.market,
                d.symbol,
                d.engine_qty,
                d.exchange_qty,
            )
    else:
        log.info("boot recovery: positions reconciled, no drift")
    return discrepancies

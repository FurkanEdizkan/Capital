# Venue API features — offered vs. used

A per-venue inventory of what each trading API *can* do, and what Capital
*actually uses* today. The gap is the roadmap: most of the API is untapped.

> Provider APIs and product availability change — and regional rules vary.
> Treat this as a decision-level summary; verify specifics against each
> provider's live docs before building on them.

> Capital currently supports **Binance only**. The `Venue` abstraction is
> preserved so additional venues can be re-added as one new implementation
> plus a registry entry. See [abstraction.md](abstraction.md) and
> [research.md](research.md) for the design and the broader multi-venue
> survey.

## Why this matters

Capital deliberately integrated a **thin, safe slice** of Binance to ship a
working system. "Capital trades on Binance" really means *spot and USDⓈ-M
futures market data plus MARKET orders* — a fraction of Binance's API. This
document makes that explicit so expansion is a deliberate choice, not a
surprise.

## Binance — offered vs. used

Binance is **far more than a futures exchange**. Its API spans several product
lines:

| Binance product | What it is | Capital uses it? |
|-----------------|------------|------------------|
| **Spot** | Direct buy/sell of crypto held in your Binance account | ✅ market data + MARKET orders |
| **USDⓈ-M Futures** | USDT/USDC-margined perpetuals & futures | ✅ market data + MARKET orders |
| **COIN-M Futures** | Coin-margined futures | ❌ |
| **Margin** | Borrow to trade spot with leverage | ❌ |
| **Options** | European-style crypto options | ❌ |
| **Convert / Buy Crypto** | One-click swaps, card purchases | ❌ |
| **Earn / Staking / Sub-accounts / Withdrawals** | Account & yield features | ❌ |

**Order types:** Binance supports MARKET, LIMIT, STOP_LOSS, TAKE_PROFIT,
trailing and OCO orders, plus futures-only controls (leverage, margin mode,
position mode, reduce-only). Capital's `BinanceVenue` places **MARKET orders
only** and rejects LIMIT; futures leverage/margin config exists but is not set
by the engine.

**On "direct coin buy to your wallet":** spot trading *is* a direct coin buy —
but the coin lands in your **Binance account**, which Binance custodies. Moving
it to a self-custody wallet needs the **withdrawal** API permission, which the
[setup guide](binance-setup.md) deliberately tells you not to enable. A
manual-buy + self-custody-withdrawal flow is a separate capability — see
roadmap.

**Market data Capital uses:** klines (spot & futures), 24h tickers, funding
rates, order-book depth, live WebSocket ticker streams. Untapped: trades,
mark/index price streams, full depth, account-data user streams.

## Summary — the untapped surface

| Theme | Status |
|-------|--------|
| Binance spot & USDⓈ-M futures, MARKET orders | ✅ in use |
| LIMIT / STOP / bracket orders | ❌ roadmap |
| Binance margin, options, COIN-M | ❌ not planned |
| Binance tokenized stocks (Ondo / Alpha) | ❌ deferred — separate venue surface |
| Manual spot buy + self-custody withdrawal | ❌ roadmap |
| Additional venues (US equities, prediction markets, …) | ❌ deferred — re-added on top of solid Binance base |

The roadmap items are tracked as GitHub issues; see the project board.

# Venue API features — offered vs. used

A per-venue inventory of what each trading API *can* do, and what Capital
*actually uses* today. The gap is the roadmap: most of each API is untapped.

> Provider APIs and product availability change — and regional rules vary.
> Treat this as a decision-level summary; verify specifics against each
> provider's live docs before building on them.

## Why this matters

Capital deliberately integrated a **thin, safe slice** of each venue to ship a
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
| **Tokenized stocks** | On-chain tokens tracking real equities — AAPLon, TSLAon, NVDAon, QQQon… via the Ondo Finance partnership on **Binance Alpha** (2026; not US-available) | ❌ — see roadmap |
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

## Alpaca — offered vs. used

| Alpaca capability | Offered | Capital uses it? |
|-------------------|---------|------------------|
| **US equities** (stocks, ETFs, fractional shares) | ✅ | ✅ bars, latest trade, MARKET orders, positions |
| **Options** (US equity options) | ✅ | ❌ |
| **Crypto** (~20 coins) | ✅ | ❌ (Capital uses Binance for crypto) |
| **Order types** | MARKET, LIMIT, STOP, STOP_LIMIT, trailing, bracket | ❌ MARKET only |
| **Paper environment** | ✅ free, global | ✅ maps to Capital's Testnet mode |
| **Account data / corporate actions / watchlists** | ✅ | ❌ |

Alpaca is commission-free and its paper account mirrors live — the
lowest-friction second asset class. `AlpacaVenue` covers stock bars, latest
trade, MARKET orders and positions; options and crypto are untouched.

## Polymarket — offered vs. used

| Polymarket capability | Offered | Capital uses it? |
|-----------------------|---------|------------------|
| **CLOB market data** (price history, midpoint, books) | ✅ | ✅ price history + midpoint |
| **Order placement** (limit & market on the CLOB) | ✅ | ✅ MARKET via the signing client |
| **Positions** (on-chain, per wallet) | ✅ via data API | ✅ for reconciliation |
| **WebSocket feed** | ✅ | ❌ (REST polling only) |
| **Sandbox / paper** | ❌ none exists | — Sim mode only |

A Polymarket "symbol" is an outcome **token id**; prices are probabilities in
0..1; collateral is USDC and settlement is on-chain. Auth is wallet-based
(L1 → L2), not key/secret — see [polymarket-setup.md](polymarket-setup.md).

## Summary — the untapped surface

| Theme | Status |
|-------|--------|
| Binance spot & USDⓈ-M futures, MARKET orders | ✅ in use |
| LIMIT / STOP / bracket orders (all venues) | ❌ roadmap |
| Binance margin, options, COIN-M | ❌ not planned |
| Binance tokenized stocks (Ondo / Alpha) | ❌ roadmap — a path to equities without Alpaca |
| Manual spot buy + self-custody withdrawal | ❌ roadmap |
| Alpaca / Polymarket as a selectable active venue | ❌ implemented but not wired into routing |

The roadmap items are tracked as GitHub issues; see the project board.

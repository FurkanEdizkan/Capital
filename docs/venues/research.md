# Venue research — open trading APIs

Phase 8 expands Capital beyond Binance to **stocks, stock-index futures and
prediction markets**. This is the research deliverable: a survey of brokers
and markets with open trading APIs, a comparison on the axes that matter for
this platform, and a recommendation for the first targets.

> Pricing, regional rules and API surfaces change. Treat the specifics below
> as a decision-level summary — verify current details against each provider's
> docs before implementation.

## What Capital needs from a venue

The existing architecture (executors, market-data client, accounting,
risk manager, allocator) sets hard requirements for any new venue:

- **Programmatic REST + streaming API** for market data and order placement.
- **A paper / sandbox environment.** Capital's safety model defaults to
  Sim → Testnet → Live; a venue with no test environment is a poor fit.
- **Key-based auth** that can be stored encrypted and used headless 24/7.
- **Instrument metadata** — tick size, lot/contract size, min notional — so
  the existing order-sizing logic carries over.
- **A fee model** that can be expressed for net-of-fees accounting.

## Stocks & stock futures

| Provider | Assets | API style | Paper/sandbox | Auth | Notes |
|----------|--------|-----------|---------------|------|-------|
| **Alpaca** | US stocks, ETFs, options, crypto | Clean REST + WebSocket | **Yes** — free paper account | API key/secret | Commission-free; excellent docs; **no futures**; mostly US |
| **Interactive Brokers** | Global stocks, options, **futures**, FX, bonds | Web API, or TWS/Client Portal Gateway | **Yes** — paper account | Gateway session / OAuth | Widest coverage incl. futures; heaviest integration (a gateway or session lifecycle) |
| **Tradier** | US stocks, options | Simple REST | **Yes** — sandbox | OAuth token | Easy API; **no futures**; US-only |
| **tastytrade** | US stocks, options, **futures** | REST + streaming | Limited | Session token | Futures + equities in one API; smaller ecosystem |
| **Tradovate** | **Futures** (CME etc.) | REST + WebSocket | **Yes** — demo | Token | Futures-specialised; good fit for an index-futures venue |

### Reading

- **Alpaca** is the strongest first **stock** venue: a modern REST+WS API, a
  free paper environment that mirrors live, simple key auth, and no
  commissions. It does not offer futures.
- **Stock-index futures** need a different provider. **Interactive Brokers**
  has the broadest reach but the heaviest integration (it expects a running
  gateway or a managed session). **Tradovate** is futures-specialised with a
  straightforward token API and a demo environment — a lighter first step.
- **Tradier** is a clean equities API but adds nothing Alpaca lacks, so it is
  a fallback rather than a first target.

## Prediction markets

| Provider | API | Sandbox | Auth | Notes |
|----------|-----|---------|------|-------|
| **Polymarket** | **CLOB API** — REST + WebSocket, central limit order book | No true paper mode | Wallet-derived API credentials (EIP-712 signing) | USDC collateral, settles on Polygon; on-chain; regional restrictions apply |

### Reading

Polymarket's **CLOB API** is a genuine order-book API — order placement,
cancellation and a market-data feed — which maps cleanly onto Capital's
executor/market-data interfaces. Two friction points stand out:

- **No sandbox.** Orders are real and settle on-chain in USDC. Capital's
  Sim mode (paper fills on live prices) partly compensates, but there is no
  venue-side test environment.
- **Wallet-based auth.** Credentials derive from an Ethereum wallet and
  requests are signed (EIP-712), unlike the API-key model used elsewhere.
  The `Venue` abstraction must not assume key/secret auth.

## Recommended first targets

1. **Alpaca — stocks.** Lowest-friction venue: modern API, free paper
   trading, key auth that drops straight into the encrypted key store. Proves
   the `Venue` abstraction against a second asset class with minimal risk.
2. **Polymarket — prediction markets.** The CLOB API fits the order-book
   model, and it exercises the abstraction's harder cases (wallet auth, no
   sandbox, on-chain settlement) — valuable to surface early.
3. **Futures — deferred within Phase 8.** Pick up after Alpaca and Polymarket,
   choosing between **Tradovate** (lighter, futures-only) and **Interactive
   Brokers** (broadest, heaviest) once the abstraction has settled.

## Implications for the Venue abstraction (issue #46)

The survey shows the `Venue` interface must not bake in Binance assumptions:

- **Auth is not always key/secret** — Polymarket signs with a wallet. The
  abstraction needs a per-venue credential type, not a fixed pair.
- **Instruments differ** — crypto pairs, shares, futures contracts and
  market outcomes need a common instrument descriptor (symbol, tick size,
  size increment, min notional) without venue-specific fields leaking out.
- **Not every venue has a sandbox** — the mode model (Sim/Testnet/Live) must
  allow a venue that supports only Sim + Live.
- **Fee models vary** — commission-free, per-share, per-contract, maker/taker
  — so the fee model is a per-venue strategy object.

These feed directly into the `Venue` interface designed in issue #46.

## Binance tokenized stocks — research spike (issue #118)

Binance revived tokenized US equities in 2026 through an **Ondo Global Markets**
partnership: on-chain tokens fully backed by shares held with a regulated
custodian (AAPLon, GOOGLon, TSLAon, NVDAon, AMZNon, METAon, MSFTon, QQQon, …).
They trade on the **Binance Alpha** platform — a surface integrated into the
Binance exchange that lets users trade on-chain tokens with funds from their
Binance account, no separate Web3 wallet.

**Spike question:** do these trade via the standard spot REST API (`/api/v3/`)
or a separate API? **Answer: a separate API.**

### Findings

1. **Not the spot API.** Tokenized stocks are *not* standard spot symbols on
   `/api/v3/`. Binance Alpha is a distinct trading surface with its own API.
2. **Binance Alpha API.** Base path
   `https://www.binance.com/bapi/defi/v1/public/alpha-trade/…`. Documented
   market-data endpoints: `token-list`, `get-exchange-info`, `klines`,
   `24hr-ticker`, plus a WebSocket feed.
3. **Symbol format.** Not `BASEQUOTE` like spot — it is
   `ALPHA_<token_id><quote_asset>` (e.g. `ALPHA_173USDT`). A `token-list` call
   maps human symbols → token IDs first.
4. **Market data is public, no auth** — read access (prices, candles,
   instrument info) needs no credentials, like Binance public spot data.
5. **Order placement is the open risk.** The *public* Alpha docs cover
   market data only. A documented, public order-placement REST endpoint for
   Alpha was **not** confirmed — order flow may go through the Binance Wallet
   or an authenticated endpoint outside the standard developer docs. This must
   be confirmed before any live order routing is built.
6. **Settlement.** Tokens are on-chain and balances sit in the Binance account;
   whether they appear in the standard spot `account` endpoint is unconfirmed —
   reconciliation/`positions()` handling depends on this.
7. **Regional.** Not available to US users; select jurisdictions only.

### Recommendation — Outcome B: a separate `BinanceAlphaVenue`

The Alpha API is a distinct surface (different base path, symbol scheme, and
likely auth) — by Capital's own abstraction that makes it a separate **venue**,
not a new `Market` value on `BinanceVenue`. Extending the `Market` enum would
ripple through ~6 `BinanceClient` methods and the hardcoded spot/futures
WebSocket hubs for no benefit.

Implement `engine/venues/binance_alpha.py` as a `Venue`:

- **Phase 1 — read-only.** Market data (`candles`, `price`, `instrument`) via
  the public Alpha endpoints + the `token-list` symbol mapping. Tradeable in
  **Sim mode** immediately (Capital's simulator fills on live Alpha prices).
- **Phase 2 — live orders.** Only once the Alpha order-placement API and its
  auth model are confirmed. Until then `place_order` raises `VenueError`
  ("read-only — Alpha order API not yet wired"), exactly as `PolymarketVenue`
  does without a signing client.

This keeps #118 shippable (Sim-mode tokenized-stock trading) without blocking on
the unconfirmed trading API, and composes cleanly with the per-venue credential
store and router wiring from #120.

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

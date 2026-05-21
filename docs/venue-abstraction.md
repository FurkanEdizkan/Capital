# Venue abstraction — design

Phase 8 expands Capital beyond Binance. The [`Venue`](../engine/venues/base.py)
interface is how: every trading venue implements one contract, and the rest of
the engine never learns which venue it is talking to.

This document is the design (issue #46). The interface lands here; the
Binance/Alpaca/Polymarket implementations and the engine rewiring follow as
separate issues.

## The interface

`engine/venues/base.py` defines:

- **`Venue`** — an ABC with five methods: `instrument`, `candles`, `price`,
  `place_order`, `positions`. Class attributes `name` and `supports_sandbox`
  identify the venue and declare whether it has a paper environment.
- **`Instrument`** — normalised instrument metadata (symbol, base, quote,
  tick size, size step, min notional), so the shared order-sizing logic works
  for a crypto pair, a share, a futures contract or a market outcome alike.
- **`VenueCandle`** — a venue-neutral OHLCV bar.
- **`OrderRequest` / `OrderResult`** — a trade intent and its fill; the fill
  carries the venue's actual `fee`.
- **`OrderType`**, **`VenueError`**.

## What stays venue-agnostic

These components already make no Binance assumptions and do **not** change:

- The strategy framework (`BaseStrategy`, indicators, built-ins, plugins).
- The risk manager (sizing, SL/TP, kill switch).
- Accounting, the position-attribution sub-ledger and the capital allocator.
- The backtest runner (it has its own `FeeModel` for estimating costs).

They operate on the engine's own types; only the layer that *fetches data and
places orders* becomes venue-pluggable.

## How today's code maps onto a `Venue`

| Today (Binance-specific) | Behind the `Venue` interface |
|--------------------------|------------------------------|
| `exchange.client.BinanceClient` | a `BinanceVenue` implementation |
| `SymbolFilters` (`get_symbol_filters`) | `Venue.instrument()` → `Instrument` |
| `Kline` / `get_klines` | `Venue.candles()` → `VenueCandle` |
| ticker price lookups | `Venue.price()` |
| `LiveExecutor` / `TestnetExecutor` order placement | `Venue.place_order()` → `OrderResult` |
| `reconcile.get_futures_positions` | `Venue.positions()` |

The Sim executor stays as-is — simulation is venue-independent (paper fills on
whatever venue's candles).

## Constraints carried from the research (#45)

The venue survey surfaced three things the interface deliberately accounts for:

- **Auth is not always key/secret.** Polymarket signs requests with an
  Ethereum wallet. The `Venue` ABC takes **no credentials** — each
  implementation's constructor accepts whatever it needs, so the abstraction
  never assumes a key/secret pair.
- **Not every venue has a sandbox.** `supports_sandbox` lets the Sim/Testnet/
  Live mode model offer only the modes a venue actually has.
- **Fee models vary** (commission-free, per-share, per-contract, maker/taker).
  The realised fee rides on `OrderResult.fee`; backtest fee *estimation* stays
  the backtest runner's separate `FeeModel`.

## Migration plan — complete

1. ✅ **`Venue` interface** — landed (#46).
2. ✅ **`BinanceVenue`** — Binance wrapped as the first venue, no behaviour
   change.
3. ✅ **Rewire the engine** — the trading engine, market-data `/klines` API,
   reconciliation and order execution all depend on a `Venue` rather than
   `BinanceClient` + executors directly (#110).
4. ✅ **Add venues** — `AlpacaVenue` (stocks) and `PolymarketVenue` (prediction
   markets) are implemented behind the interface.
5. ✅ **UI** — a venue selector on Settings; Markets / Strategies / History show
   the active venue.

Keeping each venue behind this interface is what made the expansion additive
rather than a rewrite.

### Known follow-ups

- **Routing is Binance-only.** `VenueRouter` and `ExecutorRouter` wire only
  Binance — selecting Alpaca or Polymarket as the active venue falls back to
  Binance with a warning. Wiring those venues (with their credential handling)
  is tracked separately.
- **Market-data API:** only `/klines` is venue-routed; tickers, funding and
  order-book endpoints are still Binance-specific.
- **Testnet/Live execution** is code-complete but not yet exercised against a
  real venue. See [venue-api-features.md](venue-api-features.md).

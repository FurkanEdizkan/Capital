# Venue abstraction — design

The [`Venue`](../../engine/venues/base.py) interface is how Capital stays
venue-pluggable: every trading venue implements one contract, and the rest of
the engine never learns which venue it is talking to.

This document is the abstraction's design (issue #46). Capital ships
**Binance** (crypto) and **Polymarket** (prediction markets); additional
venues are one new implementation file plus a registry entry. See
[research.md](research.md) for the original multi-venue survey that informed
the abstraction's shape.

## Per-strategy venue routing

Venue routing is **per strategy**, not a global switch: every strategy (and
stored `StrategyInstance`) carries a `venue`, and the engine resolves both the
market-data venue and the order executor per strategy each tick. Binance and
Polymarket strategies therefore run side by side in the same loop. The
`active_venue` setting remains the default for anything that does not name a
venue (e.g. manual orders from the Markets page). In Testnet mode a venue
without a sandbox (Polymarket) falls back to Sim with a warning.

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
the active venue's candles).

## Constraints carried from the research

The original venue survey (see [research.md](research.md)) surfaced three
things the interface deliberately accounts for:

- **Auth is not always key/secret.** Some venues use wallet signing or
  multi-step credential derivation. The `Venue` ABC takes **no credentials** —
  each implementation's constructor accepts whatever it needs, so the
  abstraction never assumes a key/secret pair.
- **Not every venue has a sandbox.** `supports_sandbox` lets the
  Sim/Testnet/Live mode model offer only the modes a venue actually has.
- **Fee models vary** (commission-free, per-share, per-contract, maker/taker).
  The realised fee rides on `OrderResult.fee`; backtest fee *estimation* stays
  the backtest runner's separate `FeeModel`.

## Re-adding a venue

The abstraction is intentionally preserved for this. To bring an additional
venue back online:

1. Add `<name>.py` under `engine/venues/` implementing the `Venue` ABC.
2. Append a `VenueInfo(...)` entry to `AVAILABLE_VENUES` in
   `engine/venues/registry.py`.
3. Add the new class to `_VENUE_CLASSES` in `engine/venues/factory.py` and
   add a `build_venue` branch wiring its credentials.
4. Add the venue's setup guide under `docs/venues/`.
5. Add hermetic unit tests under `engine/tests/`.

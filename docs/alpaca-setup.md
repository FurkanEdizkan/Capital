# Connecting to Alpaca

How Capital talks to [Alpaca](https://alpaca.markets/) — the US-equities venue —
and how to obtain API keys for paper or live trading.

> ⚠ **Not yet selectable.** `AlpacaVenue` is implemented and unit-tested, but
> the engine's `VenueRouter` only wires Binance today — selecting Alpaca as the
> active venue currently falls back to Binance with a warning. This guide
> describes credential setup so it is ready when the venue is wired in (tracked
> in the venue-routing issue). See [venue-abstraction.md](venue-abstraction.md).

## Modes at a glance

| Mode | What it does | API key |
|------|--------------|---------|
| **Sim** | Paper trading on live market prices — Capital's own simulator | None |
| **Testnet** | Real orders against Alpaca's **paper** environment | Paper key |
| **Live** | Real orders with real money | Live key |

Alpaca's "paper account" is its sandbox — it maps onto Capital's **Testnet**
mode. Unlike Binance, the paper environment is part of the same dashboard.

## 1. Create an account

1. Sign up at <https://alpaca.markets/>. A **paper-only** account can be
   created by anyone, anywhere, with just an email — no funding or identity
   check. Live trading requires a funded US brokerage account.
2. Capital trades **US equities** through Alpaca; trading is commission-free.

## 2. Generate API keys

Keys are created from the Alpaca dashboard. **Paper and live keys are
separate** — a paper key only works against the paper endpoint.

1. Open the dashboard and switch to the **Paper Trading** view (do this first).
2. Under **API Keys**, generate a key — you get a **Key ID** and a **Secret
   Key**. The secret is shown **once**; copy it immediately.
3. For live trading later, repeat from the live view to get a separate live
   key pair.

Alpaca authenticates with two headers — `APCA-API-KEY-ID` and
`APCA-API-SECRET-KEY` — which is what `AlpacaVenue` sends.

## 3. Endpoints

`AlpacaVenue` targets these hosts (no configuration needed):

| Purpose | Paper | Live |
|---------|-------|------|
| Trading (orders, positions, assets) | `paper-api.alpaca.markets` | `api.alpaca.markets` |
| Market data (bars, latest trade) | `data.alpaca.markets` | `data.alpaca.markets` |

Market data uses the same host for both modes; only the trading host changes.

## 4. Store the key in Capital

As with Binance, keys are entered through the dashboard (**Settings**), never in
`.env`, and are **encrypted at rest** (Fernet, keyed by `CAPITAL_SECRET_KEY`).

## Security notes

- Start on the **paper** key and stay there until a strategy is proven.
- A live Alpaca key can place orders on a real brokerage account — treat it
  like the Binance live key: admin-only, encrypted, never committed.
- `CAPITAL_SECRET_KEY` encrypts the stored key — back it up separately from the
  database (see [backup-and-restore.md](backup-and-restore.md)).

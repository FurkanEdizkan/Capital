# Connecting to Binance

How Capital talks to Binance, and how to set up API keys for Testnet or live
trading.

## Modes at a glance

| Mode | What it does | API key |
|------|--------------|---------|
| **Sim** | Paper trading on live market prices — the default | None |
| **Testnet** | Real orders against Binance Testnet (test funds) | Testnet key |
| **Live** | Real orders with real money | Live key |

Capital defaults to **Sim**. Stay on Sim and Testnet for a meaningful period
before considering live capital.

## Market data needs no key

Prices, candlestick history, funding rates and order-book depth come from
Binance's **public** endpoints — the engine's [`BinanceClient`](../engine/exchange/client.py)
uses a keyless client for them. The Markets page and Sim-mode paper trading
work out of the box with nothing to configure.

API keys are only needed to place **orders** (Testnet or Live).

## 1. Create an API key

### Testnet (do this first)

- **Spot testnet** — <https://testnet.binance.vision/>: sign in and generate a
  HMAC-SHA256 key.
- **Futures testnet** — <https://testnet.binancefuture.com/>: register, then
  find the API key in the account panel.

Testnet keys are separate from live keys and trade only fake funds.

### Live

1. Go to **API Management** — <https://www.binance.com/en/my/settings/api-management>.
2. Create an API key and enable **Spot & Margin Trading** and/or **Futures**.
3. **Do not enable withdrawals.**
4. Restrict the key to your machine's IP address if you can.

## 2. Store the key in Capital

Keys are entered through the dashboard, never in `.env`:

1. Log in as an **admin** operator.
2. Go to **Settings → Binance API keys**.
3. Paste the API key and secret, and **Save**.

The credentials are **encrypted at rest** (Fernet, keyed by `CAPITAL_SECRET_KEY`)
and never returned to the browser. The status badge shows whether keys are set.

## 3. Switch the trading mode

In **Settings → Trading mode**, pick Sim, Testnet or Live.

- A mode switch is **blocked while positions are open** — paper and real state
  must never mix, so flatten first.
- Switching to **Live** requires typing `LIVE` to confirm.

## Current status

> ⚠ **Order routing is simulated for now.** The Testnet and Live executors,
> encrypted key storage and the mode toggle are all built and tested, but the
> running engine still executes every tick through the **simulator** — the
> live executor is not yet wired into the trading loop. Setting Testnet/Live
> stores the mode and keys but does not yet place real orders. Connecting the
> executor selection to the stored mode is a tracked follow-up.

## Security notes

- Create Binance keys **without withdrawal permission**, and IP-restrict them.
- `CAPITAL_SECRET_KEY` encrypts the stored keys. Back it up **separately** from
  the database — without it a restored database cannot decrypt them
  (see [backup-and-restore.md](backup-and-restore.md)).
- Keys are admin-only to set and are never logged or exposed by the API.

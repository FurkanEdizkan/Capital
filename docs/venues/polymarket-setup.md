# Connecting to Polymarket

How Capital talks to [Polymarket](https://polymarket.com/) — the prediction-market
venue — and how to obtain the credentials it needs.

> ⚠ **No sandbox.** Polymarket has **no paper environment** — every order is
> real and settles on-chain in USDC. In Capital's mode model Polymarket
> supports only **Sim** (Capital's own simulator on live prices) and **Live**;
> in Testnet mode Polymarket strategies fall back to Sim with a warning.

Polymarket strategies run **side by side** with Binance ones: each strategy
carries its own venue, so market data and orders route per strategy — there is
no global switch to flip. Market data (the market catalogue, prices, history)
is **public and needs no credentials**; the credential set below is required
only for **live** order placement.

## What the Polymarket section does

- **Discovery** — the engine pulls the most-traded markets from the public
  Gamma API on a schedule into a local catalogue; browse and search them on
  the **Polymarket** page and pin markets to the **watchlist**.
- **AI bet analysis** — on the screening schedule (and on demand) the
  configured report-writer LLM estimates each market's true probability from
  matched news headlines and market context; the **edge** is the estimate
  minus the market price. Analyses that clear the operator's edge and
  confidence bars become pending **AI signals** (Telegram + dashboard) you
  confirm or dismiss.
- **Automated trading** — the **Prediction AI** strategy type trades one
  outcome token on the stored analyses, through the same allocation, risk and
  notify/auto machinery as every other strategy.
- **Resolution** — watched/held markets are re-checked hourly; when one
  resolves, held tokens settle at 1/0 USDC into the ledger and you are
  alerted. Live tokens may still need redemption on polymarket.com.

Cadences and bars are configured on the Settings page (Polymarket card).

## How Polymarket auth differs

Polymarket is not an API-key/secret venue like Binance. It is an on-chain
order book (CLOB) on **Polygon**, and auth has two levels:

- **L1 — wallet signing.** Your Ethereum/Polygon wallet's private key signs an
  EIP-712 message. This is used once to create or derive API credentials, and
  to sign the orders themselves. Trading stays non-custodial — the private key
  never leaves your control.
- **L2 — API credentials.** L1 yields a triple — **apiKey, secret, passphrase**.
  Every trading request is then signed with these via HMAC-SHA256. The secret
  is used to sign but is never sent over the wire.

The `Venue` abstraction was designed for this — it does not assume a fixed
key/secret pair (see [research.md](research.md)).

## 1. Prepare a wallet

1. You need a **Polygon mainnet** wallet (chain ID `137`) funded with **USDC**
   for collateral (and a little MATIC for gas).
2. Log in at <https://polymarket.com/> with that wallet **at least once** — the
   funder address must exist in your Polymarket profile before credentials can
   be created.

## 2. Create API credentials (L1 → L2)

Use the official [`py-clob-client`](https://github.com/Polymarket/py-clob-client)
SDK, which handles the EIP-712 signing:

```bash
pip install py-clob-client
```

```python
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key="YOUR_WALLET_PRIVATE_KEY",  # L1 — used only to derive credentials
)
creds = client.create_or_derive_api_key()
# creds → apiKey, secret, passphrase  (the L2 credential triple)
```

Alternatively, generate them from your Polymarket account settings, or via the
REST endpoints `POST /auth/api-key` (create) and `GET /auth/derive-api-key`
(retrieve) with the proper L1 headers.

## 3. Store the credentials in Capital

On **Settings → Venue credentials → polymarket**, store five fields,
**encrypted at rest** (Fernet, keyed by `CAPITAL_SECRET_KEY`):

| Field | What it is |
|-------|------------|
| `private_key` | The wallet's private key — signs orders (EIP-712) |
| `api_key`, `api_secret`, `passphrase` | The L2 credential triple |
| `wallet_address` | The Polymarket (proxy) wallet that holds the USDC — also enables position reads for reconciliation |

Live orders are placed only when **all five** fields are stored; otherwise the
venue stays read-only and Sim trading continues to work.

## Security notes

- The **wallet private key** is the most sensitive secret here — it controls
  real on-chain funds. Use a dedicated trading wallet, not a primary wallet,
  and fund it with only what the strategy needs.
- There is no withdrawal-permission toggle as on Binance — a compromised wallet
  key is a full compromise. Keep it encrypted and never commit it.
- Polymarket has **regional restrictions** — confirm availability in your
  jurisdiction before funding a wallet.

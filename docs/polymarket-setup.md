# Connecting to Polymarket

How Capital talks to [Polymarket](https://polymarket.com/) — the prediction-market
venue — and how to obtain the credentials it needs.

> ⚠ **Not yet selectable.** `PolymarketVenue` is implemented and unit-tested,
> but the engine's `VenueRouter` only wires Binance today — selecting Polymarket
> as the active venue currently falls back to Binance with a warning. This guide
> describes credential setup so it is ready when the venue is wired in.

> ⚠ **No sandbox.** Polymarket has **no paper environment** — every order is
> real and settles on-chain in USDC. In Capital's mode model Polymarket
> supports only **Sim** (Capital's own simulator on live prices) and **Live**;
> there is no Testnet.

## How Polymarket auth differs

Polymarket is not an API-key/secret venue like Binance or Alpaca. It is an
on-chain order book (CLOB) on **Polygon**, and auth has two levels:

- **L1 — wallet signing.** Your Ethereum/Polygon wallet's private key signs an
  EIP-712 message. This is used **once** to create or derive API credentials.
  Trading stays non-custodial — the private key never leaves your control.
- **L2 — API credentials.** L1 yields a triple — **apiKey, secret, passphrase**.
  Every trading request is then signed with these via HMAC-SHA256. The secret
  is used to sign but is never sent over the wire.

The `Venue` abstraction was designed for this — it does not assume a fixed
key/secret pair (see [venue-research.md](venue-research.md)).

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

Capital stores the L2 triple (apiKey, secret, passphrase) plus the wallet
address, **encrypted at rest** (Fernet, keyed by `CAPITAL_SECRET_KEY`). The
wallet address also enables position reads for reconciliation.

`PolymarketVenue` reads public market data (midpoints, price history) without
credentials; the credentials are needed only to place orders.

## Security notes

- The **wallet private key** is the most sensitive secret here — it controls
  real on-chain funds. Use a dedicated trading wallet, not a primary wallet,
  and fund it with only what the strategy needs.
- There is no withdrawal-permission toggle as on Binance — a compromised wallet
  key is a full compromise. Keep it encrypted and never commit it.
- Polymarket has **regional restrictions** — confirm availability in your
  jurisdiction before funding a wallet.

# Futures & perpetuals

Capital can trade USDⓈ-M perpetual futures alongside spot. Futures are
**leveraged** — gains and losses are amplified, and a position can be
liquidated. Treat them with extra care.

## Before you start

1. Enable **futures** on your Binance API key (see the *Binance API key* guide).
2. Set risk limits under **Settings → Risk**: a position-size cap, a stop-loss
   percentage, and a daily-loss kill switch. These apply to every order,
   manual or automated.
3. Stay in **Sim** mode until the behaviour matches your expectations.

## Placing a trade

- **Manual**: from **Markets**, pick a perpetual symbol and place a buy/sell.
- **Automated**: assign a strategy to a futures symbol and give it an
  allocation.

Every order — spot or futures — passes the same risk manager, so the kill
switch and size cap can never be bypassed.

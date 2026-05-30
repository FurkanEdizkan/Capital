# Running Capital

Capital is self-hosted: it runs on your own machine or a VPS and keeps trading
even when the dashboard is closed.

## Local

```bash
make up      # builds images, starts Postgres + engine + dashboard
make logs    # follow logs
make down    # stop everything
```

The dashboard is served on `http://localhost` and the engine API on port 8000.

## VPS (recommended if Binance is blocked locally)

1. Provision a small VPS in a region where Binance is reachable.
2. Clone the repo, copy `.env.example` to `.env`, and set strong values for
   `CAPITAL_JWT_SECRET` and `CAPITAL_SECRET_KEY`.
3. Run `make up`. Put it behind the bundled Caddy reverse proxy for TLS.

## Backups

`scripts/backup.sh` dumps the database; `scripts/restore.sh` restores it. Keep
`CAPITAL_SECRET_KEY` safe — without the exact key a restore cannot decrypt your
stored API credentials.

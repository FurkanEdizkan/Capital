# Capital docs

Quick navigation. For the project itself see the [main README](../README.md).

## Project mechanics

- [Architecture](architecture.md) — engine + web + Postgres, modules, data flow
- [Branching model](branching.md) — two-trunk: `test` -> `main`
- [Pull request guidelines](pull-requests.md)
- [Releases](releases.md)
- [Development setup](development.md) — manual setup, project structure

## Operations

- [Deployment](operations/deployment.md) — Tailscale / cloud VM / Let's Encrypt
- [Backup and restore](operations/backup-and-restore.md)

## Venues

Capital supports Binance (crypto) and Polymarket (prediction markets). Each
strategy carries its own venue, so strategies on different venues run side by
side in the same engine loop.

- [Binance setup](venues/binance-setup.md) — crypto
- [Polymarket setup](venues/polymarket-setup.md) — prediction markets, AI bet analysis
- [Venue abstraction](venues/abstraction.md) — the common interface
- [Venue API features](venues/api-features.md) — what Binance offers vs. what Capital uses
- [Venue research](venues/research.md) — original multi-venue survey (audit trail)

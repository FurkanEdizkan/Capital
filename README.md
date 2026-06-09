<div align="center">

# Capital

**Self-hosted automated trading platform for Binance, Alpaca, and Polymarket.**

[![CI](https://github.com/FurkanEdizkan/Capital/actions/workflows/ci.yml/badge.svg)](https://github.com/FurkanEdizkan/Capital/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/conventional%20commits-1.0.0-orange.svg)](https://www.conventionalcommits.org/en/v1.0.0/)

</div>

---

Capital runs 24/7 on your own machine, trades on configurable and code-defined
strategies, and ships with a dark dashboard for monitoring markets, positions
and PnL. It defaults to **simulation** — no real money moves until you
explicitly opt in to Testnet or live trading behind safeguards.

> ⚠️ **Trading involves risk.** Capital is provided as-is. Run it in Sim or
> Testnet mode for a meaningful period before considering any live capital.

## What it does

- **Always-on trading** — a background engine ticks every enabled strategy on a
  schedule, independent of whether the dashboard is open.
- **Strategies your way** — built-in indicator strategies (MA crossover, RSI,
  MACD, Bollinger breakout, DCA) plus a plugin loader for custom code strategies.
- **Three modes** — Simulation (paper trading on live prices) → Binance Testnet
  → Live, with explicit safeguards before real money is involved.
- **Live market data** — spot and USDⓈ-M futures prices, candlestick charts,
  funding rates and order-book depth.
- **Honest accounting** — every fill records its fee; PnL is always reported
  net of fees, and money math uses `Decimal` throughout.
- **Capital allocation** — assign a budget per strategy; the engine enforces it.
- **Multi-venue** — Binance (crypto), Alpaca (US stocks), Polymarket (prediction
  markets), behind a common venue interface.
- **AI strategies** — LLM-driven strategies with per-strategy model selection,
  daily spend caps, and a per-model performance rollup.
- **Roles & audit** — JWT login with `admin` / `user` roles; config changes are
  recorded in an audit log.

## Architecture

Capital is a monorepo of two long-lived services plus a database:

```text
┌────────────┐     REST + WebSocket      ┌────────────┐
│    web     │ ◀───────────────────────▶ │   engine   │
│ React + UI │                           │  FastAPI   │
└────────────┘                           │  + bot     │
                                         └─────┬──────┘
                                               │ SQLModel
                                         ┌─────▼──────┐
                                         │ PostgreSQL │
                                         └────────────┘
```

- **`engine/`** — the bot. Python 3.12 + FastAPI: market-data streams, the
  strategy tick loop, executors (Sim/Testnet/Live), accounting and the API.
- **`web/`** — the control panel. React 19 + Vite + TypeScript dark dashboard.
  Closing the browser never stops trading.
- **PostgreSQL** — strategies, trades, positions, candle cache and equity
  history. Schema managed with Alembic migrations.

See [docs/architecture.md](docs/architecture.md) for a fuller breakdown.

## Quick start

The fastest path is the single installer — it builds the images, starts
PostgreSQL, the engine and the dashboard, and applies database migrations.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with the
Docker Compose v2 plugin.

```bash
git clone https://github.com/FurkanEdizkan/Capital.git
cd Capital
scripts/install.sh
```

When it finishes:

| Service    | URL                          |
|------------|------------------------------|
| Dashboard  | <http://localhost:5173>      |
| API + docs | <http://localhost:8000/docs> |

Log in with the admin credentials from `.env` (`CAPITAL_ADMIN_USERNAME` /
`CAPITAL_ADMIN_PASSWORD`). The installer creates `.env` from
[`.env.example`](.env.example) on first run.

```bash
scripts/install.sh          # development mode — hot reload
scripts/install.sh prod     # production-style mode — built assets

docker compose logs -f      # follow logs
docker compose down         # stop the stack
docker compose down -v      # stop and wipe the database
```

## Configuration

All configuration lives in `.env` (gitignored). Copy
[`.env.example`](.env.example) and adjust:

| Variable                                | Purpose                                   |
|-----------------------------------------|-------------------------------------------|
| `POSTGRES_USER` / `_PASSWORD` / `_DB`   | PostgreSQL credentials                    |
| `ENGINE_PORT` / `WEB_PORT`              | Host ports for the API and dashboard      |
| `CAPITAL_ENVIRONMENT`                   | `development` or `production`             |
| `CAPITAL_JWT_SECRET`                    | JWT signing secret — **change this**      |
| `CAPITAL_ADMIN_USERNAME` / `_PASSWORD`  | Seeded admin operator                     |
| `CAPITAL_STRATEGY_PLUGINS_DIR`          | Where custom strategy plugins are scanned |

## Connecting a venue

Market data needs no API key — Sim-mode paper trading works out of the box.
Placing orders on Testnet or Live needs venue credentials, entered (encrypted)
through the Settings page.

- [docs/venues/binance-setup.md](docs/venues/binance-setup.md) — Binance (crypto)
- [docs/venues/alpaca-setup.md](docs/venues/alpaca-setup.md) — Alpaca (US stocks)
- [docs/venues/polymarket-setup.md](docs/venues/polymarket-setup.md) — Polymarket (prediction markets)
- [docs/venues/api-features.md](docs/venues/api-features.md) — what each venue API offers vs. what Capital uses

## Deployment

Run the stack privately over Tailscale, or on a public cloud VM with a real
domain and Let's Encrypt TLS — see [docs/operations/deployment.md](docs/operations/deployment.md).

## Working on Capital

For local development outside Docker (running engine and web directly), the
project structure, and the layout of `docs/`, see
[docs/development.md](docs/development.md).

## Custom strategies

Drop a Python module into `engine/strategies/plugins/` exposing a `build()`
function that returns strategy instances — the engine auto-discovers it on
startup. See [`engine/strategies/plugins/README.md`](engine/strategies/plugins/README.md)
and the [`_example.py`](engine/strategies/plugins/_example.py) template.

## Contributing

Contributions are welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). In short:

- **Branch off `test`, open PRs into `test`.** Never PR into `main` —
  `main` is promoted from `test` automatically once CI is green. See
  [docs/branching.md](docs/branching.md).
- Commits follow [Conventional Commits](https://www.conventionalcommits.org).
- Run `ruff` + `pytest` (engine) and `npm run lint` + `build` (web) before a PR.
- PRs are merged with a **merge commit** — branches are kept.

### For contributors using Claude Code

Project skills (Conventional Commits, Conventional Branches, modular service
design) live in the [My-Skills](https://github.com/FurkanEdizkan/My-Skills)
plugin marketplace, pre-registered in [`.claude/settings.json`](.claude/settings.json).
Claude Code will offer to trust + install them the first time you open this
repo — no manual step required. See [AGENTS.md](AGENTS.md) for the full agent
guide.

### For AI agents and automated contributors

Capital is designed to be navigable and contributable by AI agents:

- **API** — the engine serves an OpenAPI spec and interactive docs at
  `/docs`; every endpoint is typed and authenticated.
- **Contribution loop** — pick an issue, create a `<type>/<short-slug>` branch
  off `test`, implement with tests, open a PR with `Closes #<issue>`, and let
  CI gate the merge. This mirrors the human workflow exactly.
- **Conventions** — Conventional Commit messages, `ruff`-clean Python, hermetic
  tests. CI enforces all three, so a green build means the change is
  contract-compliant.
- An **MCP server** (`mcp_server.py`) exposes read / manage / trade tools for
  external agents, authenticated with role-scoped API tokens.

## Documentation

- [Architecture](docs/architecture.md) — how Capital is put together
- [Branching model](docs/branching.md) — the `test → main` workflow
- [Pull request guidelines](docs/pull-requests.md)
- [Releases](docs/releases.md)
- [Development setup](docs/development.md) — manual setup, project structure
- [Operations](docs/operations/) — deployment, backup & restore
- [Venues](docs/venues/) — Binance / Alpaca / Polymarket setup + design
- [Contributing](CONTRIBUTING.md) — dev setup and PR rules
- [Security policy](SECURITY.md)
- [Agent guide](AGENTS.md)

## Roadmap

| Phase | Scope                                         | Status      |
|-------|-----------------------------------------------|-------------|
| 0     | Scaffold, CI/CD, auth & roles                 | Done        |
| 1     | Live market data + Markets page               | Done        |
| 2     | Paper-trading engine + accounting + Dashboard | Done        |
| 3     | Strategy system + risk management             | Done        |
| 4     | Backtesting                                   | Done        |
| 5     | Live trading (Testnet → real)                 | Done        |
| 6     | 24/7 hardening, resilience, deployment        | Done        |
| 7     | AI strategies + agent/MCP integration         | Done        |
| 8     | Multi-venue expansion (stocks, Polymarket)    | Done        |

## License

[Apache 2.0](LICENSE) © 2026 Furkan Edizkan

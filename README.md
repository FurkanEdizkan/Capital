# Capital

[![CI](https://github.com/FurkanEdizkan/Capital/actions/workflows/ci.yml/badge.svg)](https://github.com/FurkanEdizkan/Capital/actions/workflows/ci.yml)

**Capital** is a self-hosted, automated trading platform for Binance. It runs
24/7 on your own machine, trades on configurable and code-defined strategies,
and ships with a dark dashboard for monitoring markets, positions and PnL.

It defaults to **simulation** — no real money moves until you explicitly opt in
to Testnet or live trading behind safeguards.

> ⚠️ **Trading involves risk.** Capital is provided as-is. Run it in Sim or
> Testnet mode for a meaningful period before considering any live capital.

---

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

## Manual setup (without Docker)

For working on a single service directly — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide.

```bash
docker compose up -d postgres        # database only

cd engine                            # Python engine — uses `uv`
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload     # http://localhost:8000

cd web                               # React dashboard
npm install
npm run dev                          # http://localhost:5173
```

## Custom strategies

Drop a Python module into `engine/strategies/plugins/` exposing a `build()`
function that returns strategy instances — the engine auto-discovers it on
startup. See [`engine/strategies/plugins/README.md`](engine/strategies/plugins/README.md)
and the [`_example.py`](engine/strategies/plugins/_example.py) template.

## Project structure

```text
Capital/
├── engine/            Python trading engine + API
│   ├── api/           REST + WebSocket endpoints
│   ├── auth/          JWT login, roles, audit log
│   ├── exchange/      Binance REST/WebSocket client
│   ├── marketdata/    candle cache + streaming
│   ├── strategies/    strategy framework, built-ins, plugin loader
│   ├── trading/       engine loop, executors, portfolio, accounting
│   └── tests/         pytest suite
├── web/               React + Vite + TypeScript dashboard
├── scripts/           install.sh and operational scripts
├── docker-compose.yml base service definitions
└── .github/           CI workflows, issue & PR templates
```

## Contributing

Capital is built through a tracked issue → branch → PR workflow. Both human and
automated contributors are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for
the full guide; the essentials:

- `main` is protected — all changes land via Pull Request.
- Branch names: `<type>/<issue#>-<slug>` (e.g. `feat/12-binance-client`).
- Commits follow [Conventional Commits](https://www.conventionalcommits.org).
- Run `ruff` + `pytest` (engine) and `npm run lint` + `build` (web) before a PR.
- PRs are merged with a **merge commit** — branches are kept.

### For AI agents and automated contributors

Capital is designed to be navigable and contributable by AI agents:

- **API** — the engine serves an OpenAPI spec and interactive docs at
  `/docs`; every endpoint is typed and authenticated.
- **Contribution loop** — pick an issue, create a `<type>/<issue#>-<slug>`
  branch, implement with tests, open a PR with `Closes #<issue>`, and let CI
  gate the merge. This mirrors the human workflow exactly.
- **Conventions** — Conventional Commit messages, `ruff`-clean Python, hermetic
  tests. CI enforces all three, so a green build means the change is contract-
  compliant.
- An **MCP server** exposing read/manage/trade tools for external agents is
  planned (Phase 7).

## Roadmap

| Phase | Scope                                         | Status      |
|-------|-----------------------------------------------|-------------|
| 0     | Scaffold, CI/CD, auth & roles                 | Done        |
| 1     | Live market data + Markets page               | Done        |
| 2     | Paper-trading engine + accounting + Dashboard | Done        |
| 3     | Strategy system + risk management             | In progress |
| 4     | Backtesting                                   | Planned     |
| 5     | Live trading (Testnet → real)                 | Planned     |
| 6     | 24/7 hardening, resilience, deployment        | Planned     |
| 7     | AI strategies + agent/MCP integration         | Planned     |
| 8     | Multi-venue expansion (stocks, Polymarket)    | Future      |

## License

See [LICENSE](LICENSE).

# Development

For working on Capital outside of Docker — running engine and web directly on the host — plus a reference for how the codebase is laid out. The contribution workflow (branching, commits, PRs) lives in [CONTRIBUTING.md](../CONTRIBUTING.md); the system shape lives in [architecture.md](architecture.md).

## Manual setup (without Docker)

For working on a single service directly:

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

## Project structure

```text
Capital/
├── engine/                 Python trading engine + API
│   ├── ai/                 LLM provider adapters + AI strategy support
│   ├── api/                REST + WebSocket endpoints
│   ├── auth/               JWT login, roles, API tokens, audit log
│   ├── backtest/           historical backtest runner
│   ├── exchange/           Binance REST/WebSocket client
│   ├── marketdata/         candle cache + streaming
│   ├── notify/             Telegram notifications
│   ├── ops/                boot recovery, watchdog, retention
│   ├── strategies/         strategy framework, built-ins, plugin loader
│   ├── trading/            engine loop, executors, portfolio, risk, accounting
│   ├── mcp_server.py       MCP server — the API as agent tools
│   └── tests/              pytest suite
├── web/                    React + Vite + TypeScript dashboard
├── scripts/                install.sh, deploy.sh, backup/restore
├── caddy/                  reverse-proxy config for production
├── docs/
│   ├── architecture.md     system shape
│   ├── branching.md        two-trunk workflow
│   ├── pull-requests.md    PR checklist
│   ├── releases.md         versioning + tagging
│   ├── development.md      this file
│   ├── operations/         deployment, backup & restore
│   └── venues/             Binance / Alpaca / Polymarket setup + design
├── docker-compose.yml      base service definitions
└── .github/                CI workflows, issue & PR templates
```

# Architecture

Capital is a self-hosted automated trading platform. It runs 24/7 as a small
monorepo of two long-lived services plus a database.

## Overview

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

The **engine** is the only component that talks to venues (Binance, Alpaca,
Polymarket). The **web** dashboard is purely a client of the engine's API —
closing the browser never stops trading. **PostgreSQL** holds strategies,
trades, positions, candle cache and equity history; the schema is managed with
Alembic migrations.

## Components

| Component | Responsibility | Location |
| --------- | -------------- | -------- |
| Engine API | REST + WebSocket surface for the dashboard and external agents | `engine/api/` |
| Strategy tick loop | Schedules indicator / AI strategies, applies risk + allocation, routes orders | `engine/trading/`, `engine/strategies/` |
| Venues | Binance / Alpaca / Polymarket adapters behind a common interface | `engine/exchange/`, `engine/strategies/plugins/` |
| Market data | Candle cache + live streams | `engine/marketdata/` |
| Auth | JWT login, roles, API tokens, audit log | `engine/auth/` |
| Accounting | Honest PnL (Decimal-based), equity snapshots | `engine/trading/` |
| MCP server | Same API exposed as agent tools | `engine/mcp_server.py` |
| Web dashboard | React 19 + Vite + TypeScript control panel | `web/` |
| Database | PostgreSQL 17, Alembic migrations | `engine/alembic/` |

## Data flow

A typical tick:

1. Scheduler in `engine/trading/` ticks each enabled strategy on its interval.
2. The strategy reads candles from the cache (or live stream) for its venue.
3. It produces an intended action (buy / sell / hold) with sizing.
4. The risk manager applies SL/TP, allocation caps, and the kill switch.
5. The mode's executor (Sim / Testnet / Live) places the order through the
   active venue.
6. Fills are recorded; PnL, equity, and the audit log update.
7. The web dashboard receives updates over WebSocket and re-renders.

Source diagrams for the doc set live in [`assets/diagrams/`](../assets/diagrams/)
once added.

## Key decisions

- **Two-trunk branching** — see [branching.md](branching.md).
- **Decimal money math everywhere** — float math is a known source of PnL drift.
- **Venue abstraction** — every venue implements the same interface so the
  engine's tick loop, executors, and reconciliation are venue-agnostic.
- **Schema-first API contract** — the engine exports an OpenAPI spec the web
  consumes via generated TypeScript types; CI fails on drift.

## Roadmap

The active board lives on the GitHub Project. The high-level phases are tracked
in the [README roadmap table](../README.md#roadmap).

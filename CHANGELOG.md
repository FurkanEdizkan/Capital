# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Polymarket section** — prediction markets alongside the Binance side:
  - Restored `PolymarketVenue` (CLOB market data + wallet-signed live orders
    via `py-clob-client`) with per-venue encrypted credentials
    (`private_key`, `api_key`, `api_secret`, `passphrase`, `wallet_address`).
  - **Per-strategy venue routing**: strategies (and AI signals) carry a
    `venue`, so Binance and Polymarket strategies run side by side; Testnet
    mode falls back to Sim for venues without a sandbox. Symbol columns
    widened to 80 chars for outcome-token ids (migrations 0022–0023).
  - **Market discovery**: scheduled Gamma-API refresh into a local catalogue
    with a watchlist; new Polymarket page to browse, search and pin markets.
  - **AI bet analysis**: the report-writer LLM estimates each market's true
    probability from question-matched news headlines and market context; the
    edge (estimate − price) is stored per analysis and shown on the page.
  - **Suggestions & alerts**: a scheduled screener analyses the watchlist +
    top-volume markets; analyses clearing the configurable edge/confidence
    bars become pending AI signals (Telegram + dashboard) that execute
    through the existing risk-gated confirmation path.
  - **Prediction AI strategy**: a pickable, Polymarket-pinned strategy type
    that trades one outcome token on the stored analyses with notify/auto
    action modes, allocation, risk and loss-cap enforcement.
  - **Resolution settlement**: watched/held markets are re-checked hourly;
    on resolution, held tokens settle at 1/0 USDC into the ledger and the
    operator is alerted.

### Changed

- Adopted the [Dev-Template](https://github.com/FurkanEdizkan/Dev-Template)
  scaffolding: two-trunk branching model (`main` stable / `test` integration
  with auto-promote), `.editorconfig`, `.gitattributes`, `AGENTS.md`,
  `SECURITY.md`, expanded `docs/` (Architecture, Branching, PR guidelines,
  Releases). Migrated commitlint config to `.commitlintrc.yaml`.
- Sourced Claude skills (`conventional-commits`, `conventional-branches`,
  `modular-services`) from the [My-Skills](https://github.com/FurkanEdizkan/My-Skills)
  plugin marketplace instead of vendoring them locally.
- Reorganized `docs/` by topic into `docs/operations/` and `docs/venues/`;
  normalized naming to lowercase-kebab; trimmed `README.md` by moving manual
  setup and the project-structure tree to a new `docs/development.md`; added
  a topical `docs/README.md` index.
- Consolidated three open engine refactors (#139, #140, #141) into a single
  modular-services pass: typed `PositionFillRequest`, extracted
  `manual_order` service, and extracted `strategy_view` projection.

### Removed

- **Platform reduced to Binance only.** Removed the `AlpacaVenue`,
  `PolymarketVenue`, and `BinanceAlphaVenue` implementations and their
  dedicated tests. The `Venue` ABC and registry/factory shape are preserved
  so re-adding a venue later is one new implementation file plus a registry
  entry. Multi-venue parametrize blocks in cross-cutting tests have been
  trimmed to Binance.

## [0.2.0](https://github.com/FurkanEdizkan/Capital/compare/v0.1.0...v0.2.0) - 2026-05-22

### Added

- Read-only Binance Alpha tokenized-stocks venue ([#118](https://github.com/FurkanEdizkan/Capital/issues/118)).
- AI-provider config and API-token management UI ([#44](https://github.com/FurkanEdizkan/Capital/issues/44)).
- `AIStrategy` and the analyze-and-decide endpoint ([#41](https://github.com/FurkanEdizkan/Capital/issues/41)).
- Backtest API and page ([#27](https://github.com/FurkanEdizkan/Capital/issues/27)).
- History & Logs page with CSV export ([#39](https://github.com/FurkanEdizkan/Capital/issues/39)).
- Portfolio API + Dashboard page ([#19](https://github.com/FurkanEdizkan/Capital/issues/19), [#65](https://github.com/FurkanEdizkan/Capital/issues/65)).
- Role-scoped, revocable API tokens ([#42](https://github.com/FurkanEdizkan/Capital/issues/42)).
- Strategies management API and page ([#24](https://github.com/FurkanEdizkan/Capital/issues/24)).
- Trading-mode toggle, encrypted API keys, Settings page ([#31](https://github.com/FurkanEdizkan/Capital/issues/31)).
- Venue catalogue API and Settings venue list ([#105](https://github.com/FurkanEdizkan/Capital/issues/105)).
- **engine:** accounting layer + equity snapshots ([#18](https://github.com/FurkanEdizkan/Capital/issues/18), [#64](https://github.com/FurkanEdizkan/Capital/issues/64)).
- **engine:** `AlpacaVenue` — US stock trading ([#103](https://github.com/FurkanEdizkan/Capital/issues/103)).
- **engine:** auth, roles, JWT, audit log & user management ([#3](https://github.com/FurkanEdizkan/Capital/issues/3), [#50](https://github.com/FurkanEdizkan/Capital/issues/50)).
- **engine:** backtest runner with cost model and metrics ([#26](https://github.com/FurkanEdizkan/Capital/issues/26)).
- **engine:** Binance REST client wrapper ([#9](https://github.com/FurkanEdizkan/Capital/issues/9), [#55](https://github.com/FurkanEdizkan/Capital/issues/55)).
- **engine:** Binance WebSocket market-data streams ([#10](https://github.com/FurkanEdizkan/Capital/issues/10), [#57](https://github.com/FurkanEdizkan/Capital/issues/57)).
- **engine:** `BinanceVenue` behind the Venue interface ([#102](https://github.com/FurkanEdizkan/Capital/issues/102)).
- **engine:** candle cache (market-data models) ([#11](https://github.com/FurkanEdizkan/Capital/issues/11), [#56](https://github.com/FurkanEdizkan/Capital/issues/56)).
- **engine:** custom strategy plugin loader ([#21](https://github.com/FurkanEdizkan/Capital/issues/21)).
- **engine:** watchdog with heartbeat ([#34](https://github.com/FurkanEdizkan/Capital/issues/34)).
- **engine:** historical kline downloader ([#25](https://github.com/FurkanEdizkan/Capital/issues/25)).
- **engine:** `LLMProvider` abstraction and adapters ([#40](https://github.com/FurkanEdizkan/Capital/issues/40)).
- **engine:** MA crossover strategy + wire the trading engine ([#17](https://github.com/FurkanEdizkan/Capital/issues/17), [#63](https://github.com/FurkanEdizkan/Capital/issues/63)).
- **engine:** market-data REST + WS API ([#12](https://github.com/FurkanEdizkan/Capital/issues/12), [#58](https://github.com/FurkanEdizkan/Capital/issues/58)).
- **engine:** MCP server exposing the platform as agent tools ([#43](https://github.com/FurkanEdizkan/Capital/issues/43)).
- **engine:** order/position reconciliation with Binance ([#30](https://github.com/FurkanEdizkan/Capital/issues/30)).
- **engine:** `PolymarketVenue` — prediction markets ([#104](https://github.com/FurkanEdizkan/Capital/issues/104)).
- **engine:** portfolio model + position-attribution sub-ledger ([#14](https://github.com/FurkanEdizkan/Capital/issues/14), [#60](https://github.com/FurkanEdizkan/Capital/issues/60)).
- **engine:** PostgreSQL service, DB layer & Alembic ([#2](https://github.com/FurkanEdizkan/Capital/issues/2), [#49](https://github.com/FurkanEdizkan/Capital/issues/49)).
- **engine:** risk manager — sizing, SL/TP and kill switch ([#23](https://github.com/FurkanEdizkan/Capital/issues/23)).
- **engine:** RSI, MACD, Bollinger and DCA strategies ([#20](https://github.com/FurkanEdizkan/Capital/issues/20)).
- **engine:** `SimExecutor` — paper fills ([#15](https://github.com/FurkanEdizkan/Capital/issues/15), [#61](https://github.com/FurkanEdizkan/Capital/issues/61)).
- **engine:** strategy framework + tick loop ([#16](https://github.com/FurkanEdizkan/Capital/issues/16), [#62](https://github.com/FurkanEdizkan/Capital/issues/62)).
- **engine:** Testnet and Live order executors ([#28](https://github.com/FurkanEdizkan/Capital/issues/28)).
- **engine:** Venue abstraction interface ([#46](https://github.com/FurkanEdizkan/Capital/issues/46)).
- **engine:** drain the in-flight tick on graceful shutdown ([#37](https://github.com/FurkanEdizkan/Capital/issues/37)).
- **engine:** per-strategy allocation and lifecycle rules ([#22](https://github.com/FurkanEdizkan/Capital/issues/22)).
- **engine:** freeze trading on a stale market feed ([#35](https://github.com/FurkanEdizkan/Capital/issues/35)).
- **engine:** orders placed through the Venue interface ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- **engine:** reconcile open positions with Binance on boot ([#33](https://github.com/FurkanEdizkan/Capital/issues/33)).
- **engine:** resolve the active venue from the persisted setting ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- **engine:** route market-data klines API through the active venue ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- **engine:** route orders through the mode's executor ([#98](https://github.com/FurkanEdizkan/Capital/issues/98)).
- **engine:** scaffold uv project + FastAPI health endpoint ([#1](https://github.com/FurkanEdizkan/Capital/issues/1), [#48](https://github.com/FurkanEdizkan/Capital/issues/48)).
- **engine:** source tick-loop candles through a Venue ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- **engine:** structured logging, retention pruning, Telegram alerts ([#38](https://github.com/FurkanEdizkan/Capital/issues/38)).
- **engine:** symbol-filter validation, clientOrderId, funding fetch ([#29](https://github.com/FurkanEdizkan/Capital/issues/29)).
- **infra:** engine + web compose services and dev override ([#6](https://github.com/FurkanEdizkan/Capital/issues/6), [#52](https://github.com/FurkanEdizkan/Capital/issues/52)).
- Active trading venue as a persisted setting ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- Manual operator-placed orders ([#119](https://github.com/FurkanEdizkan/Capital/issues/119)).
- Multi-model AI strategies with per-strategy model selection.
- Per-model AI performance rollup and decision log.
- Per-venue encrypted credential storage ([#120](https://github.com/FurkanEdizkan/Capital/issues/120)).
- Schema-first API contract pipeline ([#5](https://github.com/FurkanEdizkan/Capital/issues/5), [#54](https://github.com/FurkanEdizkan/Capital/issues/54)).
- Public cloud-VM deployment support.
- LLM usage tracking and daily spend cap.
- Trading-cost visibility on the dashboard.
- **web:** live Markets page + wire real engine auth ([#13](https://github.com/FurkanEdizkan/Capital/issues/13), [#59](https://github.com/FurkanEdizkan/Capital/issues/59)).
- **web:** venue-aware Markets, Strategies and History pages ([#110](https://github.com/FurkanEdizkan/Capital/issues/110)).
- **web:** dark UI shell, design system & routing ([#4](https://github.com/FurkanEdizkan/Capital/issues/4), [#47](https://github.com/FurkanEdizkan/Capital/issues/47)).
- Alpaca & Polymarket venue routing wiring ([#120](https://github.com/FurkanEdizkan/Capital/issues/120)).

### Fixed

- **engine:** build BinanceVenue's client lazily.

## [0.1.0] - 2026-04

Initial release. See git history for details.

[Unreleased]: https://github.com/FurkanEdizkan/Capital/compare/v0.2.0...HEAD
[0.1.0]: https://github.com/FurkanEdizkan/Capital/releases/tag/v0.1.0

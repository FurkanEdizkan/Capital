# Design: Runtime-tunable risk controls

**Date:** 2026-07-02
**Status:** Approved (design) — pending implementation plan
**Scope:** Engine + web. Make the five global risk limits in `engine/trading/risk.py`
enableable and tunable at runtime from the Settings UI, without an engine restart.

## Problem

`engine/trading/risk.py` already implements a complete, correct `RiskManager`:
stop-loss, take-profit, per-order notional cap, daily realized-loss limit, and a
drawdown kill switch. But every limit is wired only through `config.py` env
settings (`risk_*`), read **once at engine boot** (`engine.py:110`,
`self._risk = risk or RiskManager()`), and defaults to `0` = disabled. There is
no Settings UI for them, and the backtest does not simulate them.

Net effect: the safety net that most protects a solo operator's capital ships
**off**, and turning it on requires editing env + restarting the live engine —
so in practice it stays off. This design closes that gap for live trading. It
does **not** change the enforcement math, only how the limits are configured,
surfaced, and applied.

## Goals

- Risk limits are editable at runtime from the Settings page (no restart).
- Changes take effect on the next engine tick, in both sim and live modes.
- Zero surprise: nothing auto-closes until the operator explicitly enables a limit.
- Removing the "what number do I put here?" friction via recommended pre-fills.

## Non-goals (deferred)

- **Backtest simulation of the limits** — a strong follow-up (lets the operator
  tune from the historical equity curve instead of intuition), but its own effort.
- **Per-strategy risk overrides** — the `RiskManager` stays global (engine-wide),
  matching current architecture. (Per-strategy allocation + max-loss already exist
  separately via `StrategyAllocation` / `_loss_cap_breached`.)
- **Kill-switch notifications** — could reuse the notifier later; out of scope now.

## Decisions (from brainstorming)

1. **Scope B** — runtime-editable via Settings UI (not env-only, not backtest-sim).
2. **Approach #1** — the engine reads the limits from the settings store **per
   tick**, the same way `ai_action_mode` / AI spend-cap already flow store → engine.
3. **Defaults = C (hybrid)** — every limit defaults to `0` (disabled); the UI
   pre-fills a recommended value next to each toggle so behavior changes only on
   an explicit save.

## Design

### 1. Storage — settings store, no migration

The five limits become key-value entries in the existing `appsettings` store
(generic KV `settings` table + the `_decimal_setting` pattern the AI spend cap
uses), so **no Alembic migration is required** — only new keys.

| Store key | Unit | Recommended pre-fill |
|---|---|---|
| `risk_stop_loss_pct` | % of position entry value | 5% |
| `risk_take_profit_pct` | % of position entry value | 10% |
| `risk_max_drawdown_pct` | % from equity peak | 15% |
| `risk_daily_loss_limit` | quote currency (e.g. USDT) | hint: ~2% of equity (absolute; not auto-filled) |
| `risk_max_position_notional` | quote currency | hint: ~20% of equity (absolute; not auto-filled) |

Add typed getters/setters to `engine/appsettings/store.py`:
`get_risk_stop_loss_pct(session)` … `set_risk_stop_loss_pct(session, value)` etc.

**Backward-compatibility:** each getter returns the stored value when set, else
falls back to the env `settings.risk_*` value (0 unless already configured). Any
existing env-configured deployment keeps working; the store becomes the source of
truth once a value is saved through the UI.

### 2. Engine wiring — per-tick read

- Add `RiskManager.from_store(session)` (parallel to `from_settings`) reading the
  five store getters.
- In `engine.py` `_tick_strategy` (which already opens a session), build the
  manager from the store at the top of the tick rather than using a boot-time
  singleton. The uses at `engine.py:194` (`stop_order`) and `:260` (`review`)
  consume this per-tick instance.
- The `TradingEngine` constructor keeps an **optional injected `RiskManager`**
  (`risk: RiskManager | None`). When injected (tests), use it; when `None`
  (production), read from the store per tick. This keeps existing tests working.
- Enforcement math in `risk.py` is unchanged.

### 3. Settings UI — a "Risk controls" card

- New card on `web/src/pages/Settings.tsx`, following existing card/section and
  design-system patterns. Five rows: each = label + one-line description +
  a `Toggle` + a numeric input with its unit.
- Off ⇒ value `0` (disabled). Toggling on reveals the input **pre-filled with the
  recommended value** (percentages) or focused with a placeholder hint (the two
  absolute-currency limits). Numbers rendered mono/tabular per DESIGN.md.
- New typed settings endpoints on `engine/api/settings.py`:
  `RiskSettingsRead` (GET) and `RiskSettingsUpdate` (using the same HTTP method
  and shape as the existing `AiActionModeUpdate` / Polymarket settings endpoints —
  match the established convention rather than introducing a new one).
- Regenerate the web API types (`npm run gen:api`) after the endpoint lands; add
  a `fetchRiskSettings` / `updateRiskSettings` client in `web/src/lib/api/`.

### 4. Safety

- **No surprise:** all limits default to `0` / disabled; behavior changes only on save.
- **Mid-session application (documented in the UI):** changes take effect on the
  next engine tick — this is existing behavior (`stop_order` runs every tick;
  the kill switch checks live). The card carries an explicit copy line:
  *"Applies on the next tick — a stop-loss you enable may immediately close an
  already-losing position."*
- **Kill switch blocks new exposure only;** closing trades stay allowed (existing).
- **Server-side validation** in the update endpoint: reject negatives; clamp
  percentages to 0–100; require notional / loss-limit ≥ 0.
- **Works in sim and live** (the checks run inside the engine tick, which runs for
  both modes), so the operator can arm limits in simulation first.

### 5. Testing

- **Unit (engine):** store getters/setters — default, set/read round-trip, and the
  env fallback; `RiskManager.from_store` maps the five fields correctly.
- **Engine integration:** a limit changed mid-run is enforced on the next tick
  (set a stop-loss → a breaching open position closes; set a drawdown limit past
  the current drawdown → kill switch blocks new exposure). Existing `risk.py`
  enforcement tests remain the math baseline.
- **API:** `RiskSettingsUpdate` validation rejects negative / >100% values.
- **Web:** the Risk card renders, toggles pre-fill the recommended value, and save
  calls the update endpoint (following existing Settings test patterns).

## Affected files

- `engine/trading/risk.py` — add `from_store`.
- `engine/appsettings/store.py` — five getters/setters with env fallback.
- `engine/trading/engine.py` — per-tick `RiskManager.from_store` in `_tick_strategy`;
  keep optional injected override.
- `engine/api/settings.py` — `RiskSettingsRead` / `RiskSettingsUpdate` endpoints + validation.
- `web/src/pages/Settings.tsx` — Risk controls card.
- `web/src/lib/api/` — settings client additions + regenerated schema.
- Tests across the above.

## Open items to confirm at plan time

- Exact recommended pre-fill values (table above — starting point, operator-tunable).
- Whether the two absolute-currency limits should offer an equity-relative
  suggestion computed client-side, or stay a plain hint (design assumes plain hint).

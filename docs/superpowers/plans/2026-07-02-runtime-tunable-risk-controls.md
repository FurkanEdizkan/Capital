# Runtime-tunable Risk Controls — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Capital's five global risk limits (stop-loss, take-profit, order-size cap, daily-loss limit, drawdown kill switch) editable at runtime from the Settings UI, applied on the next engine tick, without an engine restart.

**Architecture:** The `RiskManager` enforcement math in `engine/trading/risk.py` is unchanged. Limits move from boot-time env config into the runtime `appsettings` key-value store (no DB migration — the store is generic KV). The engine builds a fresh `RiskManager` from the store each tick (same store→engine flow as `ai_action_mode`). A typed settings endpoint + a "Risk controls" card on the Settings page read/write them. Limits default to `0`/disabled; the UI pre-fills recommended values (no behavior change until saved). Getters fall back to the env `risk_*` value so existing env-configured deployments keep working.

**Tech Stack:** Python 3.12, SQLModel, FastAPI, Pydantic; React 19 + TypeScript + Vite; openapi-typescript for the client types; pytest.

**Spec:** `docs/superpowers/specs/2026-07-02-runtime-tunable-risk-controls-design.md`

**Conventions (verified in the codebase):**
- Store getters/setters use `get_setting`/`set_setting` + `_decimal_setting(session, key, default)` (`engine/appsettings/store.py`).
- API: per-setting `*Update` Pydantic model + `@router.put("/<name>", response_model=SettingsRead)` that calls the store setter(s), `record_audit(...)`, then returns `_read(session)`. Deps: `AdminUser`, `SessionDep`.
- Web client: `const { data, error } = await api.PUT("/api/settings/<name>", { body }); if (error) ...; return data;` (`web/src/lib/api/settings.ts`).
- Tests use the `session` and `client`/`login` fixtures in `engine/tests/conftest.py`.

---

## Task 1: Risk-limit getters/setters in the settings store

**Files:**
- Modify: `engine/appsettings/store.py`
- Test: `engine/tests/test_appsettings.py`

- [ ] **Step 1: Write the failing tests**

Add to `engine/tests/test_appsettings.py` (imports at top: extend the existing `from appsettings.store import (...)` block with the five getters/setters):

```python
def test_risk_limits_default_to_zero(session: Session) -> None:
    from appsettings.store import (
        get_risk_stop_loss_pct,
        get_risk_take_profit_pct,
        get_risk_max_drawdown_pct,
        get_risk_daily_loss_limit,
        get_risk_max_position_notional,
    )
    assert get_risk_stop_loss_pct(session) == Decimal(0)
    assert get_risk_take_profit_pct(session) == Decimal(0)
    assert get_risk_max_drawdown_pct(session) == Decimal(0)
    assert get_risk_daily_loss_limit(session) == Decimal(0)
    assert get_risk_max_position_notional(session) == Decimal(0)


def test_risk_limit_round_trip(session: Session) -> None:
    from appsettings.store import get_risk_stop_loss_pct, set_risk_stop_loss_pct
    set_risk_stop_loss_pct(session, Decimal("5"))
    assert get_risk_stop_loss_pct(session) == Decimal("5")


def test_risk_getter_falls_back_to_env_default_when_unset(session: Session) -> None:
    from appsettings.store import get_risk_stop_loss_pct
    # No stored value → the caller-supplied default (env fallback) is returned.
    assert get_risk_stop_loss_pct(session, Decimal("3")) == Decimal("3")


def test_risk_explicit_zero_overrides_env_default(session: Session) -> None:
    from appsettings.store import get_risk_stop_loss_pct, set_risk_stop_loss_pct
    set_risk_stop_loss_pct(session, Decimal("0"))  # operator deliberately disabled it
    assert get_risk_stop_loss_pct(session, Decimal("3")) == Decimal("0")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd engine && python -m pytest tests/test_appsettings.py -k risk -v`
Expected: FAIL — `ImportError: cannot import name 'get_risk_stop_loss_pct'`.

- [ ] **Step 3: Add the key constants and getters/setters**

In `engine/appsettings/store.py`, add the key constants alongside the existing ones (near `_AI_SPEND_CAP = "ai_spend_cap_usd"`):

```python
_RISK_STOP_LOSS = "risk_stop_loss_pct"
_RISK_TAKE_PROFIT = "risk_take_profit_pct"
_RISK_MAX_DRAWDOWN = "risk_max_drawdown_pct"
_RISK_DAILY_LOSS = "risk_daily_loss_limit"
_RISK_MAX_NOTIONAL = "risk_max_position_notional"
```

Add the getters/setters near the other `_decimal_setting` helpers (e.g. below `set_ai_spend_cap`). Each getter takes a `default` so callers can supply the env fallback; `_decimal_setting` returns `default` only when the key is unset (an explicitly-stored `"0"` is returned as `Decimal(0)`):

```python
def get_risk_stop_loss_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Stop-loss as a percent of a position's entry value (0 = disabled)."""
    return _decimal_setting(session, _RISK_STOP_LOSS, default)


def set_risk_stop_loss_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_STOP_LOSS, str(pct))


def get_risk_take_profit_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Take-profit as a percent of a position's entry value (0 = disabled)."""
    return _decimal_setting(session, _RISK_TAKE_PROFIT, default)


def set_risk_take_profit_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_TAKE_PROFIT, str(pct))


def get_risk_max_drawdown_pct(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Kill-switch drawdown limit as a percent from the equity peak (0 = disabled)."""
    return _decimal_setting(session, _RISK_MAX_DRAWDOWN, default)


def set_risk_max_drawdown_pct(session: Session, pct: Decimal) -> None:
    set_setting(session, _RISK_MAX_DRAWDOWN, str(pct))


def get_risk_daily_loss_limit(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Kill-switch daily realized-loss limit in quote currency (0 = disabled)."""
    return _decimal_setting(session, _RISK_DAILY_LOSS, default)


def set_risk_daily_loss_limit(session: Session, amount: Decimal) -> None:
    set_setting(session, _RISK_DAILY_LOSS, str(amount))


def get_risk_max_position_notional(session: Session, default: Decimal = Decimal(0)) -> Decimal:
    """Per-order notional cap in quote currency (0 = disabled)."""
    return _decimal_setting(session, _RISK_MAX_NOTIONAL, default)


def set_risk_max_position_notional(session: Session, amount: Decimal) -> None:
    set_setting(session, _RISK_MAX_NOTIONAL, str(amount))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd engine && python -m pytest tests/test_appsettings.py -k risk -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/appsettings/store.py engine/tests/test_appsettings.py
git commit -m "feat(risk): risk-limit getters/setters in the settings store"
```

---

## Task 2: `RiskManager.from_store`

**Files:**
- Modify: `engine/trading/risk.py`
- Test: `engine/tests/test_risk.py`

- [ ] **Step 1: Write the failing tests**

Add to `engine/tests/test_risk.py` (it already imports `RiskManager`, `Decimal`, `Session`):

```python
def test_from_store_reads_stored_limits(session: Session) -> None:
    from appsettings.store import set_risk_stop_loss_pct, set_risk_max_position_notional
    set_risk_stop_loss_pct(session, Decimal("5"))
    set_risk_max_position_notional(session, Decimal("1000"))
    rm = RiskManager.from_store(session)
    assert rm.stop_loss_pct == Decimal("5")
    assert rm.max_position_notional == Decimal("1000")
    assert rm.take_profit_pct == Decimal(0)  # unset → disabled


def test_from_store_falls_back_to_env_settings(session: Session) -> None:
    from config import Settings
    env = Settings(risk_stop_loss_pct=Decimal("7"))  # nothing stored
    rm = RiskManager.from_store(session, env)
    assert rm.stop_loss_pct == Decimal("7")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd engine && python -m pytest tests/test_risk.py -k from_store -v`
Expected: FAIL — `AttributeError: type object 'RiskManager' has no attribute 'from_store'`.

- [ ] **Step 3: Implement `from_store`**

In `engine/trading/risk.py`, add the import of the env singleton near the existing `from config import Settings`:

```python
from config import Settings, settings as _env_settings
```

Add the classmethod directly below the existing `from_settings` classmethod:

```python
    @classmethod
    def from_store(
        cls, session: Session, settings: Settings | None = None
    ) -> "RiskManager":
        """Build from the runtime settings store, falling back to env config
        for any limit the operator has not set through the UI."""
        from appsettings.store import (
            get_risk_daily_loss_limit,
            get_risk_max_drawdown_pct,
            get_risk_max_position_notional,
            get_risk_stop_loss_pct,
            get_risk_take_profit_pct,
        )

        env = settings if settings is not None else _env_settings
        return cls(
            max_position_notional=get_risk_max_position_notional(
                session, env.risk_max_position_notional
            ),
            stop_loss_pct=get_risk_stop_loss_pct(session, env.risk_stop_loss_pct),
            take_profit_pct=get_risk_take_profit_pct(session, env.risk_take_profit_pct),
            daily_loss_limit=get_risk_daily_loss_limit(session, env.risk_daily_loss_limit),
            max_drawdown_pct=get_risk_max_drawdown_pct(session, env.risk_max_drawdown_pct),
        )
```

(The `appsettings.store` import is inside the method to avoid any import-order coupling with the store module.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd engine && python -m pytest tests/test_risk.py -k from_store -v`
Expected: PASS (2 tests). Also run the full file to confirm no regressions: `python -m pytest tests/test_risk.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/trading/risk.py engine/tests/test_risk.py
git commit -m "feat(risk): RiskManager.from_store with env fallback"
```

---

## Task 3: Engine reads risk limits per tick

**Files:**
- Modify: `engine/trading/engine.py` (constructor ~line 110; `_tick_strategy` ~lines 162-260)
- Test: `engine/tests/test_trading_engine.py`

- [ ] **Step 1: Confirm the public tick method name**

Run: `cd engine && grep -n "def tick\|def _tick_strategy\|self._risk" trading/engine.py`
Expected: a public `def tick(self)` that iterates strategies and calls `_tick_strategy`; `self._risk` used at ~line 194 (`stop_order`) and ~line 260 (`review`). Use the confirmed public method name in Step 2's test (below it is written as `eng.tick()`).

- [ ] **Step 2: Write the failing test**

Add to `engine/tests/test_trading_engine.py` (imports: add `from appsettings.store import set_risk_max_position_notional`; `list_positions`, `Market`, `BuyWhenFlat`, `_engine`, `factory` already exist in the file):

```python
def test_engine_applies_store_risk_limits(factory: Any) -> None:
    # BuyWhenFlat buys qty 1 at the FakeVenue price of 100 → notional 100.
    # A stored per-order notional cap of 50 must clip the fill to qty 0.5.
    strat = BuyWhenFlat("buyer", "BTCUSDT", market=Market.spot)
    eng = _engine(factory, [strat])
    with factory() as session:
        set_risk_max_position_notional(session, Decimal("50"))
        session.commit()
    eng.tick()
    with factory() as session:
        positions = list_positions(session)
    assert len(positions) == 1
    assert positions[0].qty == Decimal("0.5")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd engine && python -m pytest tests/test_trading_engine.py -k store_risk_limits -v`
Expected: FAIL — position qty is `1` (the boot-time `RiskManager()` has all limits disabled, so the order is not capped).

- [ ] **Step 4: Refactor the engine to read per tick**

In `engine/trading/engine.py` constructor, replace the boot-time singleton line:

```python
        self._risk = risk or RiskManager()  # all limits disabled by default
```

with an override field (do NOT build a default here):

```python
        # Optional injected RiskManager (tests). When None, limits are read from
        # the settings store on every tick so UI changes apply without a restart.
        self._risk_override = risk
```

In `_tick_strategy`, immediately after the session is opened (`with self._session_factory() as session:`), build the per-tick manager:

```python
            risk = self._risk_override or RiskManager.from_store(session)
```

Then change the two use sites in `_tick_strategy` from `self._risk` to the local `risk`:

```python
            stop = risk.stop_order(position, price)
```
```python
            order = risk.review(session, order, position, price)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd engine && python -m pytest tests/test_trading_engine.py -k store_risk_limits -v`
Expected: PASS (qty == 0.5).

- [ ] **Step 6: Run the full engine + risk suites for regressions**

Run: `cd engine && python -m pytest tests/test_trading_engine.py tests/test_risk.py -v`
Expected: all PASS (tests that inject `risk=RiskManager(...)` still work via `_risk_override`).

- [ ] **Step 7: Commit**

```bash
git add engine/trading/engine.py engine/tests/test_trading_engine.py
git commit -m "feat(risk): engine reads risk limits from the store each tick"
```

---

## Task 4: Settings API — read + update risk limits

**Files:**
- Modify: `engine/api/settings.py`
- Test: `engine/tests/test_settings_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `engine/tests/test_settings_api.py` (follow the file's existing pattern; it uses the `client` fixture + `login`). If the file already has an auth helper, reuse it; otherwise use the `login(client, "admin", ADMIN_PASSWORD)` helper from `conftest.py` and send the token as a Bearer header:

```python
from conftest import ADMIN_PASSWORD, login


def _auth(client) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_read_settings_exposes_risk_limits_defaulting_to_zero(client) -> None:
    r = client.get("/api/settings", headers=_auth(client))
    assert r.status_code == 200
    body = r.json()
    assert body["risk_stop_loss_pct"] == "0"
    assert body["risk_max_position_notional"] == "0"


def test_update_risk_settings_persists_and_returns(client) -> None:
    r = client.put(
        "/api/settings/risk",
        headers=_auth(client),
        json={
            "stop_loss_pct": "5",
            "take_profit_pct": "10",
            "max_drawdown_pct": "15",
            "daily_loss_limit": "250",
            "max_position_notional": "1000",
        },
    )
    assert r.status_code == 200
    assert r.json()["risk_stop_loss_pct"] == "5"
    # persisted: a fresh read reflects it
    r2 = client.get("/api/settings", headers=_auth(client))
    assert r2.json()["risk_daily_loss_limit"] == "250"


def test_update_risk_settings_rejects_negative_and_over_100(client) -> None:
    r = client.put(
        "/api/settings/risk",
        headers=_auth(client),
        json={
            "stop_loss_pct": "-1",
            "take_profit_pct": "10",
            "max_drawdown_pct": "15",
            "daily_loss_limit": "0",
            "max_position_notional": "0",
        },
    )
    assert r.status_code == 422  # Pydantic validation
    r = client.put(
        "/api/settings/risk",
        headers=_auth(client),
        json={
            "stop_loss_pct": "150",  # > 100%
            "take_profit_pct": "10",
            "max_drawdown_pct": "15",
            "daily_loss_limit": "0",
            "max_position_notional": "0",
        },
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd engine && python -m pytest tests/test_settings_api.py -k risk -v`
Expected: FAIL — the read has no `risk_stop_loss_pct` key and `PUT /api/settings/risk` is 404/405.

- [ ] **Step 3: Add the read fields**

In `engine/api/settings.py`:

1. Ensure `Field` is imported: change `from pydantic import BaseModel` to `from pydantic import BaseModel, Field` (if `Field` is not already imported).
2. Extend the `from appsettings.store import (...)` block with the five getters and setters:
   `get_risk_stop_loss_pct, get_risk_take_profit_pct, get_risk_max_drawdown_pct, get_risk_daily_loss_limit, get_risk_max_position_notional, set_risk_stop_loss_pct, set_risk_take_profit_pct, set_risk_max_drawdown_pct, set_risk_daily_loss_limit, set_risk_max_position_notional`.
3. Import the env singleton for the UI-read fallback: `from config import settings as _env_settings`.
4. Add fields to `SettingsRead` (below `polymarket_stake`):

```python
    # Global risk limits (0 = disabled). Enforced by trading/risk.py each tick.
    risk_stop_loss_pct: Decimal
    risk_take_profit_pct: Decimal
    risk_max_drawdown_pct: Decimal
    risk_daily_loss_limit: Decimal
    risk_max_position_notional: Decimal
```

5. Populate them in `_read(session)` (inside the `SettingsRead(...)` call), passing the env values as fallbacks so the UI shows what the engine would use:

```python
        risk_stop_loss_pct=get_risk_stop_loss_pct(session, _env_settings.risk_stop_loss_pct),
        risk_take_profit_pct=get_risk_take_profit_pct(session, _env_settings.risk_take_profit_pct),
        risk_max_drawdown_pct=get_risk_max_drawdown_pct(session, _env_settings.risk_max_drawdown_pct),
        risk_daily_loss_limit=get_risk_daily_loss_limit(session, _env_settings.risk_daily_loss_limit),
        risk_max_position_notional=get_risk_max_position_notional(session, _env_settings.risk_max_position_notional),
```

- [ ] **Step 4: Add the update model + endpoint**

Add the model alongside the other `*Update` models (e.g. below `PolymarketSettingsUpdate`):

```python
class RiskSettingsUpdate(BaseModel):
    stop_loss_pct: Decimal = Field(ge=0, le=100)
    take_profit_pct: Decimal = Field(ge=0, le=100)
    max_drawdown_pct: Decimal = Field(ge=0, le=100)
    daily_loss_limit: Decimal = Field(ge=0)
    max_position_notional: Decimal = Field(ge=0)
```

Add the endpoint alongside the other `@router.put` handlers (e.g. below `update_polymarket_settings`):

```python
@router.put("/risk", response_model=SettingsRead)
def update_risk_settings(
    body: RiskSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Set the global risk limits (0 disables a limit).

    Changes apply on the next engine tick — a stop-loss you enable may
    immediately close an already-losing position.
    """
    set_risk_stop_loss_pct(session, body.stop_loss_pct)
    set_risk_take_profit_pct(session, body.take_profit_pct)
    set_risk_max_drawdown_pct(session, body.max_drawdown_pct)
    set_risk_daily_loss_limit(session, body.daily_loss_limit)
    set_risk_max_position_notional(session, body.max_position_notional)
    record_audit(
        session,
        actor=admin.username,
        action="settings.risk",
        detail={
            "stop_loss_pct": str(body.stop_loss_pct),
            "take_profit_pct": str(body.take_profit_pct),
            "max_drawdown_pct": str(body.max_drawdown_pct),
            "daily_loss_limit": str(body.daily_loss_limit),
            "max_position_notional": str(body.max_position_notional),
        },
    )
    return _read(session)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd engine && python -m pytest tests/test_settings_api.py -k risk -v`
Expected: PASS (3 tests). Then run the whole engine suite: `python -m pytest -q` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/api/settings.py engine/tests/test_settings_api.py
git commit -m "feat(risk): settings API to read and update risk limits"
```

---

## Task 5: Regenerate the web API types + add the client

**Files:**
- Regenerate: `web/openapi.json`, `web/src/lib/api/schema.d.ts`
- Modify: `web/src/lib/api/settings.ts`

- [ ] **Step 1: Regenerate the OpenAPI schema + TS types**

Find the FastAPI app object: `cd engine && grep -rn "FastAPI(" .` (expected in `main.py`, e.g. `app = FastAPI(...)`). Dump the spec and regenerate the client types:

```bash
cd engine
python -c "import json, main; open('../web/openapi.json','w').write(json.dumps(main.app.openapi()))"
cd ../web
npm run gen:api
```

Expected: `web/openapi.json` and `web/src/lib/api/schema.d.ts` now include `RiskSettingsUpdate` and the five `risk_*` fields on `SettingsRead`. Verify: `grep -n "risk_stop_loss_pct\|RiskSettingsUpdate" web/src/lib/api/schema.d.ts` prints matches.

- [ ] **Step 2: Add the client function**

Append to `web/src/lib/api/settings.ts`, mirroring `updatePolymarketSettings`:

```typescript
export async function updateRiskSettings(body: {
  stop_loss_pct: string;
  take_profit_pct: string;
  max_drawdown_pct: string;
  daily_loss_limit: string;
  max_position_notional: string;
}): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/risk", { body });
  if (error) throw new Error("Failed to update risk settings");
  return data;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: exit 0 (the new client + regenerated types compile).

- [ ] **Step 4: Commit**

```bash
git add web/openapi.json web/src/lib/api/schema.d.ts web/src/lib/api/settings.ts
git commit -m "feat(risk): regenerate API types + risk settings client"
```

---

## Task 6: Settings UI — "Risk controls" card

**Files:**
- Modify: `web/src/pages/Settings.tsx`

**Recommended pre-fill values (percentages pre-fill on enable; the two absolute-currency limits use a placeholder hint, since a sane number depends on the operator's capital):** stop-loss `5`, take-profit `10`, max-drawdown `15`; daily-loss-limit and max-position-notional start blank with hint text.

- [ ] **Step 1: Import the client + add component state**

In `web/src/pages/Settings.tsx`, add `updateRiskSettings` to the settings-client import block (which already imports `updateAiSpendCap`, `updatePolymarketSettings`, etc.). Add state near the other setting groups (e.g. below the polymarket `pm*` state):

```typescript
  // Risk controls — value "" or "0" means the limit is disabled.
  const [riskStopLoss, setRiskStopLoss] = useState("");
  const [riskTakeProfit, setRiskTakeProfit] = useState("");
  const [riskMaxDrawdown, setRiskMaxDrawdown] = useState("");
  const [riskDailyLoss, setRiskDailyLoss] = useState("");
  const [riskMaxNotional, setRiskMaxNotional] = useState("");
```

- [ ] **Step 2: Hydrate the state from loaded settings**

In the effect/handler that copies loaded `settings` into local state (where `setAiSpendCap(...)` etc. are called after `fetchSettings()`), add:

```typescript
      setRiskStopLoss(nonZero(s.risk_stop_loss_pct));
      setRiskTakeProfit(nonZero(s.risk_take_profit_pct));
      setRiskMaxDrawdown(nonZero(s.risk_max_drawdown_pct));
      setRiskDailyLoss(nonZero(s.risk_daily_loss_limit));
      setRiskMaxNotional(nonZero(s.risk_max_position_notional));
```

Add this helper near the top of the module (a "0"/"0.00" limit shows as an empty, disabled field):

```typescript
const nonZero = (v: string): string => (Number(v) > 0 ? v : "");
```

- [ ] **Step 3: Add the save handler**

Add near the other save handlers (e.g. `savePolymarket`), sending "0" for any blank (disabled) field:

```typescript
  const saveRisk = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await updateRiskSettings({
        stop_loss_pct: riskStopLoss || "0",
        take_profit_pct: riskTakeProfit || "0",
        max_drawdown_pct: riskMaxDrawdown || "0",
        daily_loss_limit: riskDailyLoss || "0",
        max_position_notional: riskMaxNotional || "0",
      });
      setSettings(next);
      setNotice("Risk controls saved — applied on the next engine tick.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save risk controls");
    } finally {
      setBusy(false);
    }
  };
```

- [ ] **Step 4: Render the card**

Add a "Risk controls" `Card` in the settings layout (follow the existing card markup — `Card` + `SectionHeader` + rows + a `Button`). Each row is a labeled numeric `Input`; a `Toggle` arms a percentage limit by pre-filling the recommended value (blank = disabled). Use the design tokens/components already in the file:

```tsx
      <Card>
        <SectionHeader
          title="Risk controls"
          subtitle="Global limits enforced before every order. 0 / off disables a limit."
        />
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ fontSize: 12, color: "var(--text-2)" }}>
            Changes apply on the next engine tick — a stop-loss you enable may
            immediately close an already-losing position.
          </div>

          <RiskRow
            label="Stop-loss"
            hint="% of entry value; force-closes a losing position"
            unit="%"
            value={riskStopLoss}
            onChange={setRiskStopLoss}
            recommended="5"
          />
          <RiskRow
            label="Take-profit"
            hint="% of entry value; force-closes a winning position"
            unit="%"
            value={riskTakeProfit}
            onChange={setRiskTakeProfit}
            recommended="10"
          />
          <RiskRow
            label="Max drawdown (kill switch)"
            hint="% from equity peak; halts new exposure"
            unit="%"
            value={riskMaxDrawdown}
            onChange={setRiskMaxDrawdown}
            recommended="15"
          />
          <RiskRow
            label="Daily loss limit (kill switch)"
            hint="quote currency; halts new exposure for the day"
            unit="USDT"
            value={riskDailyLoss}
            onChange={setRiskDailyLoss}
            placeholder="e.g. 2% of equity"
          />
          <RiskRow
            label="Max position notional"
            hint="quote currency; caps a single order's size"
            unit="USDT"
            value={riskMaxNotional}
            onChange={setRiskMaxNotional}
            placeholder="e.g. 20% of equity"
          />

          <div>
            <Button kind="primary" onClick={() => void saveRisk()} disabled={busy}>
              Save risk controls
            </Button>
          </div>
        </div>
      </Card>
```

Add the `RiskRow` helper component at the bottom of the module (a toggle that pre-fills/clears the value, plus the numeric input):

```tsx
function RiskRow({
  label,
  hint,
  unit,
  value,
  onChange,
  recommended,
  placeholder,
}: {
  label: string;
  hint: string;
  unit: string;
  value: string;
  onChange: (v: string) => void;
  recommended?: string;
  placeholder?: string;
}) {
  const enabled = Number(value) > 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <Toggle
        checked={enabled}
        onChange={(on) => onChange(on ? (recommended ?? "") : "")}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--text)" }}>{label}</div>
        <div style={{ fontSize: 11.5, color: "var(--text-2)" }}>{hint}</div>
      </div>
      <div style={{ width: 160 }}>
        <Input
          value={value}
          onChange={onChange}
          suffix={unit}
          placeholder={placeholder ?? "off"}
        />
      </div>
    </div>
  );
}
```

Note: confirm `Toggle`'s prop names and `Input`'s `onChange`/`suffix`/`placeholder` props against `web/src/components/ui.tsx` and adjust the two lines if they differ (e.g. `Toggle` may take `label`; `Input` `onChange` is `(value: string) => void`). These components are already used elsewhere in `Settings.tsx`, so mirror an existing call site.

- [ ] **Step 5: Typecheck + lint**

Run: `cd web && npm run typecheck && npm run lint`
Expected: exit 0 for both (pre-existing react-refresh warnings are acceptable; no new errors).

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Settings.tsx
git commit -m "feat(risk): Risk controls card on the Settings page"
```

---

## Task 7: Final verification

- [ ] **Step 1: Full engine test suite**

Run: `cd engine && python -m pytest -q`
Expected: all PASS.

- [ ] **Step 2: Web typecheck + lint + build**

Run: `cd web && npm run typecheck && npm run lint && npm run build`
Expected: typecheck/lint exit 0; `vite build` succeeds.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Start the app (`cd web && npm run dev` + the engine), open Settings → Risk controls, toggle stop-loss on (pre-fills 5), save, confirm the notice, reload, confirm the value persists. Switch to sim mode and confirm an armed limit is respected on the next tick.

---

## Self-review notes (author)

- **Spec coverage:** storage (T1), from_store + env fallback (T2), per-tick engine read + injected override preserved (T3), API read/update + validation (T4), regenerated client (T5), Settings UI card with hybrid recommended pre-fills + "applies next tick" warning (T6), tests throughout, final verification (T7). Non-goals (backtest sim, per-strategy, notifications) intentionally excluded.
- **No migration** — the store is generic KV; confirmed via `_decimal_setting`/`set_setting`.
- **Backward-compat** — getters take an env-default arg; `from_store` and `_read` both pass the env `risk_*` values, so a value shows/enforces identically whether it came from env or the store.
- **Open confirmations flagged inline:** the public tick method name (T3 S1), the FastAPI app import path for the openapi dump (T5 S1), and `Toggle`/`Input` prop names (T6 S4) — each has a concrete grep/verification step rather than an assumption.

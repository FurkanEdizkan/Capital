/**
 * Strategy Lab — compare strategies × coins by gain and risk, ask the AI for
 * a recommendation, and apply any winning row as a live (sim) strategy.
 *
 * Two pivots over the same backtest grid:
 *  - "By coin": one coin, every strategy type (plus the AI pick).
 *  - "By strategy": one type, several coins — where does it perform best?
 */
import { useEffect, useMemo, useState } from "react";

import { GuideButton } from "../components/GuideModal";
import { I } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  Modal,
  SectionHeader,
  SegmentedControl,
} from "../components/ui";
import {
  type CompareCell,
  compareGrid,
  type Recommendation,
  recommendStrategy,
} from "../lib/api/lab";
import {
  createStrategy,
  fetchStrategyTypes,
  type StrategyType,
} from "../lib/api/strategies";

const TIMEFRAMES = ["15m", "1h", "4h", "1d"];

function Spark({ points }: { points: number[] }) {
  if (points.length < 2) return <span style={{ color: "var(--text-4)" }}>—</span>;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 90;
  const h = 24;
  const path = points
    .map(
      (p, i) =>
        `${((i / (points.length - 1)) * w).toFixed(1)},${(h - ((p - min) / range) * h).toFixed(1)}`,
    )
    .join(" ");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline
        points={path}
        fill="none"
        stroke={up ? "var(--green)" : "var(--red)"}
        strokeWidth={1.4}
      />
    </svg>
  );
}

function Num({ value, suffix = "%", invert = false }: {
  value: number | string;
  suffix?: string;
  invert?: boolean;
}) {
  const n = Number(value);
  const good = invert ? n <= 0 : n >= 0;
  return (
    <span className="num" style={{ color: good ? "var(--green)" : "var(--red)" }}>
      {n.toFixed(2)}
      {suffix}
    </span>
  );
}

type Row = CompareCell & { ai?: boolean; reasoning?: string };

export function Lab() {
  const [pivot, setPivot] = useState<"coin" | "strategy">("coin");
  const [types, setTypes] = useState<StrategyType[]>([]);
  const [typeKey, setTypeKey] = useState("ma_cross");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [symbolsRaw, setSymbolsRaw] = useState("BTCUSDT, ETHUSDT, SOLUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [days, setDays] = useState("90");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [applying, setApplying] = useState<Row | null>(null);
  const [ran, setRan] = useState(false);

  useEffect(() => {
    fetchStrategyTypes().then(setTypes).catch(() => setTypes([]));
  }, []);

  const typeLabel = useMemo(
    () => Object.fromEntries(types.map((t) => [t.key, t.label])),
    [types],
  );

  const runCompare = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const cells =
        pivot === "coin"
          ? await compareGrid({
              symbols: [symbol.trim()],
              timeframe,
              days: Number(days) || 90,
            })
          : await compareGrid({
              types: [typeKey],
              symbols: symbolsRaw
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              timeframe,
              days: Number(days) || 90,
            });
      setRows(
        [...cells].sort((a, b) => Number(b.return_pct) - Number(a.return_pct)),
      );
      setRan(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setBusy(false);
    }
  };

  const askAi = async () => {
    setAiBusy(true);
    setError(null);
    try {
      const rec: Recommendation = await recommendStrategy({
        symbol: symbol.trim(),
        timeframe,
        days: Number(days) || 90,
      });
      const aiRow: Row = { ...rec.cell, ai: true, reasoning: rec.reasoning };
      setRows((prev) =>
        [aiRow, ...prev.filter((r) => !r.ai)].sort(
          (a, b) => Number(b.return_pct) - Number(a.return_pct),
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recommendation failed");
    } finally {
      setAiBusy(false);
    }
  };

  const confirmApply = async () => {
    if (!applying) return;
    const row = applying;
    setApplying(null);
    setBusy(true);
    try {
      const created = await createStrategy({
        name: `${typeLabel[row.type] ?? row.type} ${row.symbol} (lab)`,
        type: row.type,
        symbol: row.symbol,
        timeframe,
        params: Object.fromEntries(
          Object.entries(row.params as Record<string, unknown>).map(([k, v]) => [
            k,
            String(v),
          ]),
        ),
      });
      setNotice(
        `Created "${created.name}" — it trades on the next tick in the current trading mode. Manage it on Strategies.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setBusy(false);
    }
  };

  const cols: Column<Row>[] = [
    {
      key: "what",
      label: pivot === "coin" ? "Strategy" : "Coin",
      render: (r) => (
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontWeight: 600 }}>
            {pivot === "coin" ? (typeLabel[r.type] ?? r.type) : r.symbol}
            {r.ai && (
              <Badge tone="violet" style={{ marginLeft: 6 }}>
                AI pick
              </Badge>
            )}
          </span>
          {Object.keys(r.params).length > 0 && (
            <span style={{ fontSize: 10.5, color: "var(--text-3)" }} className="num">
              {Object.entries(r.params as Record<string, unknown>)
                .map(([k, v]) => `${k}=${v}`)
                .join(" · ")}
            </span>
          )}
          {r.ai && r.reasoning && (
            <span style={{ fontSize: 11, color: "var(--text-3)", maxWidth: 360 }}>
              {r.reasoning}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "equity",
      label: "Equity",
      render: (r) => <Spark points={r.equity_sparkline} />,
    },
    {
      key: "return_pct",
      label: "Return",
      align: "right",
      render: (r) =>
        r.error ? (
          <span style={{ fontSize: 11.5, color: "var(--red)" }}>{r.error}</span>
        ) : (
          <Num value={r.return_pct} />
        ),
    },
    {
      key: "max_drawdown_pct",
      label: "Max DD",
      align: "right",
      render: (r) => (
        <span className="num" style={{ color: "var(--red)" }}>
          −{Number(r.max_drawdown_pct).toFixed(2)}%
        </span>
      ),
    },
    {
      key: "sharpe",
      label: "Sharpe",
      align: "right",
      render: (r) => <span className="num">{Number(r.sharpe).toFixed(2)}</span>,
    },
    {
      key: "win_rate_pct",
      label: "Win rate",
      align: "right",
      render: (r) => <span className="num">{Number(r.win_rate_pct).toFixed(0)}%</span>,
    },
    {
      key: "trades",
      label: "Trades",
      align: "right",
      render: (r) => <span className="num">{r.trades}</span>,
    },
    {
      key: "apply",
      label: "",
      align: "right",
      render: (r) =>
        r.error ? null : (
          <Button size="sm" kind="outline" onClick={() => setApplying(r)}>
            Apply
          </Button>
        ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card padding={0}>
        <SectionHeader
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Strategy Lab <GuideButton slug="lab" />
            </span>
          }
          subtitle="Backtested gain/risk comparison — pick a winner and apply it in two clicks"
          right={
            <SegmentedControl
              size="sm"
              options={[
                { value: "coin", label: "By coin" },
                { value: "strategy", label: "By strategy" },
              ]}
              value={pivot}
              onChange={(p) => {
                setPivot(p);
                setRows([]);
                setRan(false);
              }}
            />
          }
        />
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            flexWrap: "wrap",
            padding: "12px 16px",
          }}
        >
          {pivot === "coin" ? (
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="Coin (e.g. SOLUSDT)"
              size="sm"
            />
          ) : (
            <>
              <select
                value={typeKey}
                onChange={(e) => setTypeKey(e.target.value)}
                style={labSelectStyle}
              >
                {types.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label}
                  </option>
                ))}
              </select>
              <Input
                value={symbolsRaw}
                onChange={(e) => setSymbolsRaw(e.target.value.toUpperCase())}
                placeholder="Coins, comma-separated (max 8)"
                size="sm"
                style={{ minWidth: 260 }}
              />
            </>
          )}
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            style={labSelectStyle}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
          <Input
            value={days}
            onChange={(e) => setDays(e.target.value)}
            placeholder="Days"
            size="sm"
            type="number"
            style={{ width: 90 }}
          />
          <Button size="sm" kind="primary" onClick={runCompare} disabled={busy}>
            {busy ? "Running…" : "Compare"}
          </Button>
          {pivot === "coin" && (
            <Button size="sm" kind="outline" onClick={askAi} disabled={aiBusy || !ran}>
              {aiBusy ? "Asking…" : "Ask AI for a pick"}
            </Button>
          )}
        </div>
        {error && (
          <div style={{ padding: "0 16px 12px", color: "var(--red)", fontSize: 12.5 }}>
            {error}
          </div>
        )}
        {notice && (
          <div
            style={{ padding: "0 16px 12px", color: "var(--text-2)", fontSize: 12.5 }}
          >
            {notice}
          </div>
        )}
        {rows.length === 0 ? (
          <EmptyState
            icon={<I.Backtest size={20} />}
            title={ran ? "No results" : "Run a comparison"}
            body={
              pivot === "coin"
                ? "Pick a coin to see what every strategy could gain on it, with the risk alongside."
                : "Pick a strategy to see which coins it performs best on."
            }
          />
        ) : (
          <DataTable
            columns={cols}
            rows={rows}
            rowKey={(r) => `${r.type}:${r.symbol}:${r.ai ? "ai" : "grid"}`}
            dense
          />
        )}
      </Card>

      <Modal
        open={applying !== null}
        onClose={() => setApplying(null)}
        title="Apply strategy"
        footer={
          <>
            <Button kind="ghost" onClick={() => setApplying(null)}>
              Cancel
            </Button>
            <Button kind="primary" onClick={confirmApply} disabled={busy}>
              Create strategy
            </Button>
          </>
        }
      >
        <span style={{ fontSize: 13 }}>
          Create{" "}
          <strong>
            {applying ? (typeLabel[applying.type] ?? applying.type) : ""} on{" "}
            {applying?.symbol}
          </strong>{" "}
          ({timeframe}) with the backtested parameters and a $10,000 allocation?
          It trades in the current trading mode (Sim by default) and can be
          managed — or promoted to live — from the Strategies page.
        </span>
      </Modal>
    </div>
  );
}

const labSelectStyle = {
  height: 30,
  padding: "0 10px",
  background: "#18181B",
  border: "1px solid #27272A",
  borderRadius: 6,
  color: "#E4E4E7",
  fontSize: 12,
} as const;

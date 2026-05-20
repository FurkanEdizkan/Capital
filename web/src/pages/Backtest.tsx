/**
 * Backtest — pick a strategy and date range, replay it over historical data,
 * and view the resulting equity curve, metrics and trade log.
 */
import { useCallback, useEffect, useState } from "react";

import { EquityChart } from "../components/EquityChart";
import { I } from "../components/icons";
import {
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  Money,
  SectionHeader,
  StatTile,
} from "../components/ui";
import { fmt } from "../lib/format";
import {
  type BacktestResponse,
  runBacktest,
} from "../lib/api/backtest";
import { fetchStrategies, type Strategy } from "../lib/api/strategies";

const DAY_MS = 86_400_000;
const isoDate = (ms: number) => new Date(ms).toISOString().slice(0, 10);

type BTrade = BacktestResponse["trades"][number];

export function Backtest() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategy, setStrategy] = useState("");
  const [start, setStart] = useState(isoDate(Date.now() - 90 * DAY_MS));
  const [end, setEnd] = useState(isoDate(Date.now()));
  const [capital, setCapital] = useState("10000");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    fetchStrategies()
      .then((s) => {
        setStrategies(s);
        if (s.length > 0) setStrategy((cur) => cur || s[0].name);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load strategies"));
  }, []);

  const run = useCallback(async () => {
    if (!strategy) return;
    setRunning(true);
    setError(null);
    try {
      setResult(
        await runBacktest({
          strategy,
          start: `${start}T00:00:00`,
          end: `${end}T23:59:59`,
          initial_capital: capital,
          // Cost model — engine defaults: 2bps slippage, 0.1% fee, no funding.
          slippage_bps: "2",
          fee_rate: "0.001",
          funding_rate: "0",
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backtest failed");
      setResult(null);
    } finally {
      setRunning(false);
    }
  }, [strategy, start, end, capital]);

  const tradeCols: Column<BTrade>[] = [
    {
      key: "time",
      label: "Time",
      render: (r) => <span className="num">{r.time.slice(0, 16).replace("T", " ")}</span>,
    },
    {
      key: "side",
      label: "Side",
      render: (r) => (
        <span style={{ color: r.side === "buy" ? "#34D399" : "#F87171" }}>{r.side}</span>
      ),
    },
    {
      key: "quantity",
      label: "Size",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.quantity), 4)}</span>,
    },
    {
      key: "price",
      label: "Price",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.price), 2)}</span>,
    },
    {
      key: "fee",
      label: "Fee",
      align: "right",
      render: (r) => <Money value={Number(r.fee)} />,
    },
    {
      key: "realized_pnl",
      label: "Realized PnL",
      align: "right",
      render: (r) => <Money value={Number(r.realized_pnl)} signed />,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card>
        <SectionHeader
          title="Run a backtest"
          subtitle="Replay a strategy over historical candles with a realistic cost model."
        />
        <div
          style={{
            padding: 14,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "flex-end",
          }}
        >
          <Field label="Strategy">
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              style={{
                height: 34,
                padding: "0 10px",
                background: "#18181B",
                border: "1px solid #27272A",
                borderRadius: 8,
                color: "#E4E4E7",
                fontSize: 12.5,
                minWidth: 200,
              }}
            >
              {strategies.length === 0 && <option value="">No strategies</option>}
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name} ({s.symbol})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Start">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="End">
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
          <Field label="Initial capital">
            <Input
              type="number"
              prefix="$"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
            />
          </Field>
          <Button kind="primary" onClick={() => void run()} disabled={running || !strategy}>
            {running ? "Running…" : "Run backtest"}
          </Button>
        </div>
      </Card>

      {error && <EmptyState icon={<I.Warn />} title="Backtest failed" body={error} />}

      {result && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            <StatTile
              label="Total Return"
              value={`${Number(result.metrics.total_return_pct) >= 0 ? "+" : "−"}${fmt(
                Math.abs(Number(result.metrics.total_return_pct)),
              )}%`}
              subTone={Number(result.metrics.total_return_pct) >= 0 ? "green" : "red"}
              trend={Number(result.metrics.total_return_pct) >= 0 ? "up" : "down"}
            />
            <StatTile label="Win Rate" value={`${fmt(Number(result.metrics.win_rate_pct))}%`} />
            <StatTile
              label="Max Drawdown"
              value={`−${fmt(Number(result.metrics.max_drawdown_pct))}%`}
              subTone="red"
            />
            <StatTile label="Sharpe (per-bar)" value={fmt(Number(result.metrics.sharpe), 3)} />
          </div>

          <Card>
            <SectionHeader
              title="Equity curve"
              subtitle={`${result.strategy} · ${result.symbol} · ${result.candles} candles · ${result.metrics.trades} trades`}
            />
            <div style={{ padding: 14 }}>
              <EquityChart
                points={result.equity_curve.map((p) => ({
                  time: p.time,
                  value: Number(p.equity),
                }))}
              />
            </div>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <StatTile label="Final Equity" value={`$${fmt(Number(result.final_equity))}`} />
            <StatTile
              label="Net PnL"
              value={`${Number(result.net_pnl) >= 0 ? "+" : "−"}$${fmt(
                Math.abs(Number(result.net_pnl)),
              )}`}
              subTone={Number(result.net_pnl) >= 0 ? "green" : "red"}
            />
            <StatTile label="Total Fees" value={`$${fmt(Number(result.total_fees))}`} />
          </div>

          <Card>
            <SectionHeader title="Trades" subtitle={`${result.trades.length} simulated fills`} />
            {result.trades.length === 0 ? (
              <EmptyState
                icon={<I.History />}
                title="No trades"
                body="The strategy produced no signals over this range."
              />
            ) : (
              <DataTable
                columns={tradeCols}
                rows={result.trades}
                rowKey={(r, i) => `${r.time}-${i}`}
                dense
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 11, color: "var(--text-2)" }}>{label}</span>
      {children}
    </div>
  );
}

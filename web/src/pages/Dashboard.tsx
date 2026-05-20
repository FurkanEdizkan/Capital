/**
 * Dashboard — portfolio overview: equity, PnL net of fees, open positions and
 * recent bot activity. Consumes the portfolio API; refreshes periodically.
 */
import { useCallback, useEffect, useState } from "react";

import { EquityChart } from "../components/EquityChart";
import { I } from "../components/icons";
import {
  Card,
  type Column,
  DataTable,
  EmptyState,
  SectionHeader,
  SideBadge,
  StatTile,
} from "../components/ui";
import { fmt } from "../lib/format";
import {
  type EquitySnapshot,
  fetchEquity,
  fetchPositions,
  fetchSummary,
  fetchTrades,
  type PortfolioSummary,
  type Position,
  type Trade,
} from "../lib/api/portfolio";

const REFRESH_MS = 15_000;

export function Dashboard() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [equity, setEquity] = useState<EquitySnapshot[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, e, p, t] = await Promise.all([
        fetchSummary(),
        fetchEquity(),
        fetchPositions(),
        fetchTrades(),
      ]);
      setSummary(s);
      setEquity(e);
      setPositions(p);
      setTrades(t);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  if (error && !summary) {
    return <EmptyState icon={<I.Warn />} title="Couldn't load the dashboard" body={error} />;
  }

  const net = summary ? Number(summary.net_pnl) : 0;
  const idle = summary ? Number(summary.idle_capital) : 0;

  const positionCols: Column<Position>[] = [
    { key: "strategy", label: "Strategy" },
    { key: "symbol", label: "Symbol" },
    { key: "side", label: "Side", render: (r) => <SideBadge side={r.side} /> },
    { key: "qty", label: "Size", align: "right", render: (r) => <span className="num">{fmt(Number(r.qty), 4)}</span> },
    {
      key: "entry_price",
      label: "Entry",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.entry_price), 2)}</span>,
    },
    {
      key: "realized_pnl",
      label: "Realized PnL",
      align: "right",
      render: (r) => <PnlText value={Number(r.realized_pnl)} />,
    },
  ];

  const tradeCols: Column<Trade>[] = [
    {
      key: "executed_at",
      label: "Time",
      render: (r) => <span className="num">{r.executed_at.slice(11, 19)}</span>,
    },
    { key: "strategy", label: "Strategy" },
    { key: "symbol", label: "Symbol" },
    { key: "side", label: "Side", render: (r) => <SideBadge side={r.side} /> },
    { key: "quantity", label: "Size", align: "right", render: (r) => <span className="num">{fmt(Number(r.quantity), 4)}</span> },
    {
      key: "price",
      label: "Price",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.price), 2)}</span>,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <StatTile
          label="Portfolio Value"
          value={`$${fmt(summary ? Number(summary.equity) : 0)}`}
          accent="#10B981"
        />
        <StatTile
          label="Net PnL (after fees)"
          value={`${net >= 0 ? "+" : "−"}$${fmt(Math.abs(net))}`}
          subTone={net >= 0 ? "green" : "red"}
          sub={summary ? `${summary.open_positions} open positions` : ""}
          trend={net >= 0 ? "up" : "down"}
        />
        <StatTile
          label="Total Fees Paid"
          value={`$${fmt(summary ? Number(summary.total_fees) : 0)}`}
        />
        <StatTile
          label="Allocated Capital"
          value={`$${fmt(summary ? Number(summary.total_allocated) : 0)}`}
          sub={`$${fmt(idle)} idle`}
        />
      </div>

      <Card>
        <SectionHeader title="Equity curve" subtitle="Snapshot per engine tick" />
        <div style={{ padding: 14 }}>
          <EquityChart
            points={equity.map((s) => ({ time: s.ts, value: Number(s.equity) }))}
          />
        </div>
      </Card>

      <Card>
        <SectionHeader title="Open positions" subtitle={`${positions.length} held`} />
        {positions.length === 0 ? (
          <EmptyState icon={<I.Dashboard />} title="No open positions" body="Strategies open positions as their signals fire." />
        ) : (
          <DataTable columns={positionCols} rows={positions} rowKey={(r) => r.id ?? r.symbol} dense />
        )}
      </Card>

      <Card>
        <SectionHeader title="Recent activity" subtitle="Latest executed trades" />
        {trades.length === 0 ? (
          <EmptyState icon={<I.History />} title="No trades yet" body="The bot's trades will appear here." />
        ) : (
          <DataTable columns={tradeCols} rows={trades} rowKey={(r) => r.id ?? r.executed_at} dense />
        )}
      </Card>
    </div>
  );
}

function PnlText({ value }: { value: number }) {
  const color = value > 0 ? "#34D399" : value < 0 ? "#F87171" : "var(--text-2)";
  return (
    <span className="num" style={{ color }}>
      {value >= 0 ? "+" : "−"}${fmt(Math.abs(value))}
    </span>
  );
}

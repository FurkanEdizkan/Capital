/**
 * Strategies — manage trading strategies: capital allocation, enable/disable,
 * per-strategy net PnL & fees, and closing open positions.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import { VenueBadge } from "../components/VenueBadge";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  Modal,
  Money,
  SectionHeader,
  StatTile,
  Toggle,
} from "../components/ui";
import { fmt } from "../lib/format";
import {
  closeStrategy,
  fetchStrategies,
  type Strategy,
  updateAllocation,
  updateEnabled,
} from "../lib/api/strategies";

const REFRESH_MS = 20_000;

export function Strategies() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Strategy | null>(null);
  const [allocDraft, setAllocDraft] = useState("");
  const [closing, setClosing] = useState<Strategy | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStrategies(await fetchStrategies());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load strategies");
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const act = useCallback(
    async (fn: () => Promise<void>) => {
      setBusy(true);
      try {
        await fn();
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Action failed");
      } finally {
        setBusy(false);
      }
    },
    [load],
  );

  const saveAllocation = () => {
    if (!editing) return;
    const strat = editing;
    setEditing(null);
    void act(async () => {
      await updateAllocation(strat.name, allocDraft);
      setNotice(`Updated allocation for ${strat.name}.`);
    });
  };

  const confirmClose = () => {
    if (!closing) return;
    const strat = closing;
    setClosing(null);
    void act(async () => {
      const n = await closeStrategy(strat.name);
      setNotice(`Closed ${n} position${n === 1 ? "" : "s"} for ${strat.name}.`);
    });
  };

  if (error && strategies.length === 0) {
    return <EmptyState icon={<I.Warn />} title="Couldn't load strategies" body={error} />;
  }

  const totalAllocated = strategies.reduce((s, x) => s + Number(x.allocated), 0);
  const totalNet = strategies.reduce((s, x) => s + Number(x.net_pnl), 0);
  const activeCount = strategies.filter((x) => x.enabled).length;

  const cols: Column<Strategy>[] = [
    {
      key: "name",
      label: "Strategy",
      render: (r) => (
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontWeight: 600 }}>{r.name}</span>
          <span style={{ fontSize: 11, color: "var(--text-2)" }}>{r.kind}</span>
        </div>
      ),
    },
    { key: "symbol", label: "Symbol", render: (r) => <span className="num">{r.symbol}</span> },
    {
      key: "enabled",
      label: "Enabled",
      render: (r) => (
        <Toggle
          checked={r.enabled}
          onChange={(v) => void act(async () => void (await updateEnabled(r.name, v)))}
        />
      ),
    },
    {
      key: "allocated",
      label: "Allocation",
      align: "right",
      render: (r) => (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Money value={Number(r.allocated)} />
          <Button
            size="sm"
            kind="ghost"
            onClick={() => {
              setEditing(r);
              setAllocDraft(String(Number(r.allocated)));
            }}
          >
            Edit
          </Button>
        </div>
      ),
    },
    {
      key: "net_pnl",
      label: "Net PnL",
      align: "right",
      render: (r) => <Money value={Number(r.net_pnl)} signed />,
    },
    {
      key: "fees",
      label: "Fees",
      align: "right",
      render: (r) => <Money value={Number(r.fees)} />,
    },
    {
      key: "open_positions",
      label: "Positions",
      align: "right",
      render: (r) =>
        r.open_positions > 0 ? (
          <Badge tone="blue">{r.open_positions} open</Badge>
        ) : (
          <span style={{ color: "var(--text-2)" }}>—</span>
        ),
    },
    {
      key: "actions",
      label: "",
      align: "right",
      render: (r) => (
        <Button
          size="sm"
          kind="outline"
          disabled={r.open_positions === 0 || busy}
          onClick={() => setClosing(r)}
        >
          Close
        </Button>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <StatTile label="Strategies" value={`${activeCount} / ${strategies.length} active`} />
        <StatTile label="Total Allocated" value={`$${fmt(totalAllocated)}`} />
        <StatTile
          label="Net PnL (after fees)"
          value={`${totalNet >= 0 ? "+" : "−"}$${fmt(Math.abs(totalNet))}`}
          subTone={totalNet >= 0 ? "green" : "red"}
          trend={totalNet >= 0 ? "up" : "down"}
        />
      </div>

      <Card>
        <SectionHeader
          title="Strategies"
          subtitle="Set capital allocation, enable or disable, and close open positions."
          right={<VenueBadge />}
        />
        {strategies.length === 0 ? (
          <EmptyState
            icon={<I.Strategies />}
            title="No strategies registered"
            body="Built-in and plugin strategies appear here once the engine starts."
          />
        ) : (
          <DataTable columns={cols} rows={strategies} rowKey={(r) => r.name} dense />
        )}
      </Card>

      {notice && <div style={{ fontSize: 12, color: "var(--text-2)" }}>{notice}</div>}

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing ? `Allocation — ${editing.name}` : ""}
        footer={
          <>
            <Button kind="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button kind="primary" onClick={saveAllocation} disabled={busy}>
              Save
            </Button>
          </>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--text-2)" }}>
            Capital budget (quote currency). The engine caps the strategy's
            exposure to this amount.
          </span>
          <Input
            value={allocDraft}
            onChange={(e) => setAllocDraft(e.target.value)}
            prefix="$"
            type="number"
            full
          />
        </div>
      </Modal>

      <Modal
        open={closing !== null}
        onClose={() => setClosing(null)}
        title="Close open positions"
        footer={
          <>
            <Button kind="ghost" onClick={() => setClosing(null)}>
              Cancel
            </Button>
            <Button kind="danger" onClick={confirmClose} disabled={busy}>
              Close positions
            </Button>
          </>
        }
      >
        <span style={{ fontSize: 13 }}>
          Close all {closing?.open_positions} open position
          {closing?.open_positions === 1 ? "" : "s"} held by{" "}
          <strong>{closing?.name}</strong>? This executes market orders at the
          latest price.
        </span>
      </Modal>
    </div>
  );
}

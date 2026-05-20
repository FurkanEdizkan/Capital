/**
 * Markets — live spot & futures ticker table with a candlestick detail view.
 * Consumes the market-data API: REST for the initial load + candle history,
 * and the `/ws/market` WebSocket for live ticker updates.
 */
import { useEffect, useMemo, useState } from "react";

import { CandleChart } from "../components/CandleChart";
import { I } from "../components/icons";
import {
  Badge,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  Pill,
  SectionHeader,
  SegmentedControl,
  type Sort,
  SymbolCell,
} from "../components/ui";
import { fmt, fmtCompact } from "../lib/format";
import {
  type Candle,
  fetchKlines,
  fetchTickers,
  type MarketKind,
  type Ticker,
  useTickerStream,
} from "../lib/api/market";

const TIMEFRAMES = [
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
];

export function Markets() {
  const [market, setMarket] = useState<MarketKind>("spot");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>({ key: "quote_volume_24h", dir: "desc" });
  const [selected, setSelected] = useState<string | null>(null);
  const [tf, setTf] = useState("1h");

  const stream = useTickerStream();
  const [restTickers, setRestTickers] = useState<Ticker[]>([]);
  const [restError, setRestError] = useState<string | null>(null);

  // Initial load / fallback when the live stream has no data for this market.
  useEffect(() => {
    let cancelled = false;
    setRestError(null);
    fetchTickers(market)
      .then((t) => !cancelled && setRestTickers(t))
      .catch((e) => !cancelled && setRestError(e instanceof Error ? e.message : "Error"));
    return () => {
      cancelled = true;
    };
  }, [market]);

  const liveTickers = market === "spot" ? stream.spot : stream.futures;
  const tickers = liveTickers.length ? liveTickers : restTickers;

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    const filtered = q ? tickers.filter((t) => t.symbol.includes(q)) : tickers;
    return [...filtered].sort((a, b) => {
      const av = a[sort.key as keyof Ticker];
      const bv = b[sort.key as keyof Ticker];
      const an = Number(av);
      const bn = Number(bv);
      const cmp =
        !Number.isNaN(an) && !Number.isNaN(bn)
          ? an - bn
          : String(av).localeCompare(String(bv));
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [tickers, query, sort]);

  const onSort = (key: string) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));

  const columns: Column<Ticker>[] = [
    { key: "symbol", label: "Symbol", render: (r) => <SymbolCell sym={r.symbol} /> },
    {
      key: "price",
      label: "Last price",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.price), Number(r.price) < 10 ? 4 : 2)}</span>,
    },
    {
      key: "change_pct_24h",
      label: "24h %",
      align: "right",
      render: (r) => {
        const v = Number(r.change_pct_24h);
        return (
          <span className="num" style={{ color: v >= 0 ? "#34D399" : "#F87171" }}>
            {v >= 0 ? "+" : ""}
            {fmt(v, 2)}%
          </span>
        );
      },
    },
    {
      key: "quote_volume_24h",
      label: "24h volume",
      align: "right",
      render: (r) => <span className="num">${fmtCompact(Number(r.quote_volume_24h))}</span>,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card>
        <div
          style={{
            padding: 14,
            display: "flex",
            alignItems: "center",
            gap: 12,
            borderBottom: "1px solid var(--border-soft)",
          }}
        >
          <SegmentedControl
            options={[
              { value: "spot", label: "Spot" },
              { value: "futures", label: "Futures" },
            ]}
            value={market}
            onChange={(m) => {
              setMarket(m);
              setSelected(null);
            }}
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            prefix={<I.Search />}
            placeholder="Search symbol (e.g. BTC)…"
            style={{ flex: 1, minWidth: 200 }}
          />
          <Pill>{rows.length} pairs</Pill>
          <Badge tone={stream.connected ? "green" : "muted"}>
            {stream.connected ? "Live" : "Connecting"}
          </Badge>
        </div>

        {restError && rows.length === 0 ? (
          <EmptyState
            icon={<I.Warn />}
            title="Couldn't load markets"
            body={restError}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            sort={sort}
            onSort={onSort}
            rowKey={(r) => r.symbol}
            onRowClick={(r) => setSelected(r.symbol)}
            highlightRow={(r) => r.symbol === selected}
            dense
          />
        )}
      </Card>

      {selected && (
        <Card>
          <SectionHeader
            title={selected}
            subtitle={`${market} · candles`}
            right={
              <SegmentedControl
                size="sm"
                options={TIMEFRAMES}
                value={tf}
                onChange={setTf}
              />
            }
          />
          <div style={{ padding: 14 }}>
            <CandleDetail symbol={selected} interval={tf} market={market} />
          </div>
        </Card>
      )}
    </div>
  );
}

function CandleDetail({
  symbol,
  interval,
  market,
}: {
  symbol: string;
  interval: string;
  market: MarketKind;
}) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setCandles([]);
    fetchKlines(symbol, interval, market)
      .then((c) => !cancelled && setCandles(c))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Error"));
    return () => {
      cancelled = true;
    };
  }, [symbol, interval, market]);

  if (error) {
    return <EmptyState icon={<I.Warn />} title="Couldn't load candles" body={error} />;
  }
  if (!candles.length) {
    return (
      <div style={{ height: 360, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-3)" }}>
        Loading candles…
      </div>
    );
  }
  return <CandleChart candles={candles} />;
}

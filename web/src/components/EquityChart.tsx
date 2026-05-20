/** Equity-curve area chart (lightweight-charts), themed to the dark tokens. */
import { createChart, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { EquitySnapshot } from "../lib/api/portfolio";

export function EquityChart({
  snapshots,
  height = 280,
}: {
  snapshots: EquitySnapshot[];
  height?: number;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = container.current;
    if (!el || snapshots.length === 0) return;

    const chart: IChartApi = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { color: "transparent" },
        textColor: "#A1A1AA",
        fontFamily: "JetBrains Mono, monospace",
      },
      grid: {
        vertLines: { color: "#1B1B1F" },
        horzLines: { color: "#1B1B1F" },
      },
      rightPriceScale: { borderColor: "#232328" },
      timeScale: { borderColor: "#232328", timeVisible: true },
      crosshair: { mode: 0 },
    });

    const series = chart.addAreaSeries({
      lineColor: "#10B981",
      topColor: "rgba(16,185,129,.25)",
      bottomColor: "rgba(16,185,129,.02)",
      lineWidth: 2,
    });
    // De-dup by timestamp — lightweight-charts requires strictly increasing time.
    const seen = new Set<number>();
    series.setData(
      snapshots
        .map((s) => ({
          time: Math.floor(Date.parse(s.ts) / 1000) as UTCTimestamp,
          value: Number(s.equity),
        }))
        .filter((p) => !seen.has(p.time) && seen.add(p.time)),
    );
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [snapshots, height]);

  if (snapshots.length === 0) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-3)",
          fontSize: 13,
        }}
      >
        No equity history yet — the engine records a snapshot each tick.
      </div>
    );
  }
  return <div ref={container} style={{ width: "100%", height }} />;
}

/**
 * Candlestick chart (TradingView lightweight-charts), themed to match the
 * dark design tokens.
 */
import { createChart, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { Candle } from "../lib/api/market";

export function CandleChart({ candles, height = 360 }: { candles: Candle[]; height?: number }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = container.current;
    if (!el) return;

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

    const series = chart.addCandlestickSeries({
      upColor: "#10B981",
      downColor: "#EF4444",
      borderUpColor: "#10B981",
      borderDownColor: "#EF4444",
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    series.setData(
      candles.map((c) => ({
        time: (Date.parse(c.open_time) / 1000) as UTCTimestamp,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      })),
    );
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: el.clientWidth });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [candles, height]);

  return <div ref={container} style={{ width: "100%", height }} />;
}

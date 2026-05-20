/**
 * Market-data API helpers + the live ticker WebSocket hook.
 */
import { useEffect, useRef, useState } from "react";

import { api, getAuthToken } from "./client";
import type { components } from "./schema";

export type Ticker = components["schemas"]["Ticker"];
export type Candle = components["schemas"]["Candle"];
export type OrderBook = components["schemas"]["OrderBook"];
export type MarketKind = "spot" | "futures";

export async function fetchTickers(market: MarketKind): Promise<Ticker[]> {
  const { data, error } = await api.GET("/api/market/tickers", {
    params: { query: { market } },
  });
  if (error || !data) throw new Error("Failed to load tickers");
  return data;
}

export async function fetchKlines(
  symbol: string,
  interval: string,
  market: MarketKind,
): Promise<Candle[]> {
  const { data, error } = await api.GET("/api/market/klines", {
    params: { query: { symbol, interval, market, limit: 300 } },
  });
  if (error || !data) throw new Error("Failed to load candles");
  return data;
}

export async function fetchOrderBook(
  symbol: string,
  market: MarketKind,
): Promise<OrderBook> {
  const { data, error } = await api.GET("/api/market/orderbook", {
    params: { query: { symbol, market } },
  });
  if (error || !data) throw new Error("Failed to load order book");
  return data;
}

type TickerStream = { spot: Ticker[]; futures: Ticker[]; connected: boolean };

/**
 * Subscribes to `/ws/market` for live ticker snapshots. Reconnects on drop.
 */
export function useTickerStream(): TickerStream {
  const [state, setState] = useState<TickerStream>({
    spot: [],
    futures: [],
    connected: false,
  });
  const closed = useRef(false);

  useEffect(() => {
    closed.current = false;
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const token = getAuthToken();
      if (!token || closed.current) return;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${window.location.host}/ws/market?token=${token}`);

      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data as string);
        if (msg.type === "tickers") {
          setState({
            spot: msg.payload.spot,
            futures: msg.payload.futures,
            connected: true,
          });
        }
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed.current) retry = setTimeout(connect, 2000); // self-heal
      };
    };

    connect();
    return () => {
      closed.current = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  return state;
}

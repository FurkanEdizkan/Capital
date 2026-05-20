/** Backtest API helper — run a strategy over historical data. */
import { api } from "./client";
import type { components } from "./schema";

export type BacktestRequest = components["schemas"]["BacktestRequest"];
export type BacktestResponse = components["schemas"]["BacktestResponse"];

export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  const { data, error } = await api.POST("/api/backtest/run", { body: req });
  if (error || !data) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Backtest failed";
    throw new Error(detail);
  }
  return data;
}

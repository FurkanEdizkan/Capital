/** Portfolio API helpers — accounting summary, equity, positions, trades. */
import { api } from "./client";
import type { components } from "./schema";

export type PortfolioSummary = components["schemas"]["PortfolioSummary"];
export type StrategySummary = components["schemas"]["StrategySummary"];
export type EquitySnapshot = components["schemas"]["EquitySnapshot"];
export type Position = components["schemas"]["Position"];
export type Trade = components["schemas"]["Trade"];
export type Costs = components["schemas"]["CostsRead"];

export async function fetchSummary(): Promise<PortfolioSummary> {
  const { data, error } = await api.GET("/api/portfolio/summary");
  if (error || !data) throw new Error("Failed to load portfolio summary");
  return data;
}

export async function fetchEquity(): Promise<EquitySnapshot[]> {
  const { data, error } = await api.GET("/api/portfolio/equity");
  if (error || !data) throw new Error("Failed to load equity history");
  return data;
}

export async function fetchPositions(): Promise<Position[]> {
  const { data, error } = await api.GET("/api/portfolio/positions");
  if (error || !data) throw new Error("Failed to load positions");
  return data;
}

export async function fetchTrades(): Promise<Trade[]> {
  const { data, error } = await api.GET("/api/portfolio/trades");
  if (error || !data) throw new Error("Failed to load trades");
  return data;
}

export async function fetchCosts(): Promise<Costs> {
  const { data, error } = await api.GET("/api/portfolio/costs");
  if (error || !data) throw new Error("Failed to load trading costs");
  return data;
}

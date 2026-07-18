/** Settings API helpers — trading mode and per-venue credentials. */
import { api } from "./client";
import type { components } from "./schema";

export type Settings = components["schemas"]["SettingsRead"];
export type TradingMode = Settings["mode"];

function errorDetail(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    return String((error as { detail: unknown }).detail);
  }
  return fallback;
}

export async function fetchSettings(): Promise<Settings> {
  const { data, error } = await api.GET("/api/settings");
  if (error || !data) throw new Error(errorDetail(error, "Failed to load settings"));
  return data;
}

export async function updateMode(mode: TradingMode, confirm: boolean): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/mode", {
    body: { mode, confirm },
  });
  if (error || !data) throw new Error(errorDetail(error, "Failed to change mode"));
  return data;
}

export async function updateVenueCredentials(
  venue: string,
  fields: Record<string, string>,
): Promise<void> {
  const { error } = await api.PUT("/api/settings/venue-credentials/{venue}", {
    params: { path: { venue } },
    body: { fields },
  });
  if (error) throw new Error(errorDetail(error, "Failed to save credentials"));
}

export async function updateAiSettings(
  provider: string,
  model: string,
  baseUrl: string,
  apiKey: string,
): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/ai", {
    body: { provider, model, base_url: baseUrl, api_key: apiKey },
  });
  if (error || !data) throw new Error(errorDetail(error, "Failed to save AI settings"));
  return data;
}

export async function updateAiSpendCap(cap: string): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/ai-spend-cap", {
    body: { cap },
  });
  if (error || !data) throw new Error(errorDetail(error, "Failed to set spend cap"));
  return data;
}

export async function updateAiActionMode(mode: string): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/ai-action-mode", {
    body: { mode },
  });
  if (error || !data) throw new Error(errorDetail(error, "Failed to set AI action mode"));
  return data;
}

export async function updateLlmCredentials(
  provider: string,
  apiKey: string,
  baseUrl: string,
): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/llm-credentials/{provider}", {
    params: { path: { provider } },
    body: { api_key: apiKey, base_url: baseUrl },
  });
  if (error || !data) {
    throw new Error(errorDetail(error, "Failed to save LLM credentials"));
  }
  return data;
}

export async function updateResearchSettings(body: {
  symbols: string[];
  interval_hours: number;
  writer_provider: string;
  writer_model: string;
  news_interval_hours: number | null;
}): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/research", { body });
  if (error || !data) {
    throw new Error(errorDetail(error, "Failed to save research settings"));
  }
  return data;
}

export async function updatePolymarketSettings(body: {
  refresh_hours: number;
  research_hours: number;
  edge_threshold: string;
  min_confidence: string;
  screen_top: number;
  stake: string;
}): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/polymarket", { body });
  if (error || !data) {
    throw new Error(errorDetail(error, "Failed to save Polymarket settings"));
  }
  return data;
}

export async function updateRiskSettings(body: {
  stop_loss_pct: string;
  take_profit_pct: string;
  max_drawdown_pct: string;
  daily_loss_limit: string;
  max_position_notional: string;
}): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/risk", { body });
  if (error || !data) {
    throw new Error(errorDetail(error, "Failed to update risk settings"));
  }
  return data;
}

export async function updateCouncilSettings(body: {
  members: { provider: string; model: string }[];
  quorum: string;
}): Promise<Settings> {
  const { data, error } = await api.PUT("/api/settings/council", { body });
  if (error || !data) {
    throw new Error(errorDetail(error, "Failed to save council settings"));
  }
  return data;
}

export type LocalAI = components["schemas"]["LocalAIRead"];

export async function fetchLocalAI(refresh = false): Promise<LocalAI> {
  const { data, error } = await api.GET("/api/ai/local", {
    params: { query: { refresh } },
  });
  if (error || !data) throw new Error("Failed to probe local models");
  return data;
}

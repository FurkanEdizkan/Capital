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

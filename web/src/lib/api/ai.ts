/** AI API helpers — model performance, the decision log and pending signals. */
import { api } from "./client";
import type { components } from "./schema";

export type ModelUsage = components["schemas"]["ModelUsage"];
export type LlmUsage = components["schemas"]["LLMUsage"];
export type AiSignal = components["schemas"]["AISignal"];

export async function fetchModelUsage(): Promise<ModelUsage[]> {
  const { data, error } = await api.GET("/api/ai/models");
  if (error || !data) throw new Error("Failed to load model performance");
  return data;
}

export async function fetchDecisionLog(): Promise<LlmUsage[]> {
  const { data, error } = await api.GET("/api/ai/decisions");
  if (error || !data) throw new Error("Failed to load the decision log");
  return data;
}

export async function fetchSignals(statusFilter?: string): Promise<AiSignal[]> {
  const { data, error } = await api.GET("/api/ai/signals", {
    params: { query: { status_filter: statusFilter } },
  });
  if (error || !data) throw new Error("Failed to load AI signals");
  return data;
}

export async function confirmSignal(id: number): Promise<AiSignal> {
  const { data, error } = await api.POST("/api/ai/signals/{signal_id}/confirm", {
    params: { path: { signal_id: id } },
  });
  if (error || !data) throw new Error("Failed to confirm the signal");
  return data;
}

export async function dismissSignal(id: number): Promise<AiSignal> {
  const { data, error } = await api.POST("/api/ai/signals/{signal_id}/dismiss", {
    params: { path: { signal_id: id } },
  });
  if (error || !data) throw new Error("Failed to dismiss the signal");
  return data;
}

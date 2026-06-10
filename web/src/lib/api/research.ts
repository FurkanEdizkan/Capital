/** Research API helpers — stored reports and an on-demand run. */
import { api } from "./client";
import type { components } from "./schema";

export type ResearchReport = components["schemas"]["ResearchReportRead"];

export async function fetchReports(
  symbol?: string,
  limit = 50,
): Promise<ResearchReport[]> {
  const { data, error } = await api.GET("/api/research", {
    params: { query: { symbol, limit } },
  });
  if (error || !data) throw new Error("Failed to load research reports");
  return data;
}

export async function fetchReport(id: number): Promise<ResearchReport> {
  const { data, error } = await api.GET("/api/research/{report_id}", {
    params: { path: { report_id: id } },
  });
  if (error || !data) throw new Error("Failed to load report");
  return data;
}

export async function runResearch(symbol = ""): Promise<ResearchReport[]> {
  const { data, error } = await api.POST("/api/research/run", {
    body: { symbol },
  });
  if (error || !data) throw new Error("Research run failed");
  return data;
}

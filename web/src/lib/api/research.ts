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

export type CouncilReview = components["schemas"]["CouncilReviewRead"];

/** Latest council review for a report — null when none exists yet. */
export async function fetchReview(reportId: number): Promise<CouncilReview | null> {
  const { data, error, response } = await api.GET("/api/research/{report_id}/review", {
    params: { path: { report_id: reportId } },
  });
  if (response.status === 404) return null;
  if (error || !data) throw new Error("Failed to load council review");
  return data;
}

export async function rerunReview(reportId: number): Promise<CouncilReview> {
  const { data, error } = await api.POST("/api/research/{report_id}/review", {
    params: { path: { report_id: reportId } },
  });
  if (error || !data) throw new Error("Council review failed");
  return data;
}

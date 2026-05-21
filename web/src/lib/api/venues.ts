/** Venues API helper — the catalogue of supported trading venues. */
import { api } from "./client";
import type { components } from "./schema";

export type Venue = components["schemas"]["VenueRead"];

export async function fetchVenues(): Promise<Venue[]> {
  const { data, error } = await api.GET("/api/venues");
  if (error || !data) throw new Error("Failed to load venues");
  return data;
}

export async function setActiveVenue(venue: string): Promise<Venue[]> {
  const { data, error } = await api.PUT("/api/venues/active", { body: { venue } });
  if (error || !data) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Failed to switch venue";
    throw new Error(detail);
  }
  return data;
}

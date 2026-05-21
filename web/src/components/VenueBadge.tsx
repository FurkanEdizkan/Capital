/**
 * VenueBadge — shows the platform's active trading venue.
 *
 * Markets, Strategies and History are venue-aware: the data they show is
 * sourced from whichever venue is active, so each page surfaces it. The
 * active venue is set on the Settings page; this badge is read-only.
 */
import { useEffect, useState } from "react";

import { fetchVenues } from "../lib/api/venues";

export function VenueBadge() {
  const [venue, setVenue] = useState<{ name: string; asset_class: string } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    fetchVenues()
      .then((venues) => {
        const active = venues.find((v) => v.active);
        if (!cancelled && active) {
          setVenue({ name: active.name, asset_class: active.asset_class });
        }
      })
      .catch(() => {
        /* the badge is non-critical — stay hidden if venues can't be loaded */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!venue) return null;

  return (
    <span
      title={`Active venue — data on this page is sourced from ${venue.name}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        fontSize: 11,
        fontWeight: 500,
        color: "var(--text-2)",
        background: "rgba(255,255,255,.03)",
        border: "1px solid var(--border)",
        borderRadius: 999,
        padding: "3px 10px",
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: 999,
          background: "#34D399",
          boxShadow: "0 0 6px rgba(52,211,153,.7)",
        }}
      />
      <span style={{ color: "var(--text-3)", fontFamily: "var(--mono)" }}>VENUE</span>
      <span style={{ textTransform: "capitalize" }}>{venue.name}</span>
      <span style={{ color: "var(--text-4)" }}>·</span>
      <span style={{ color: "var(--text-3)" }}>{venue.asset_class}</span>
    </span>
  );
}

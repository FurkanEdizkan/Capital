/**
 * Guide — a directory of the in-app setup and how-to walkthroughs. Pick one
 * on the left to read it; the same content backs the "?" buttons across the app.
 */
import { useState } from "react";

import { GUIDES, GuideContent, type GuideSlug } from "../components/GuideModal";
import { Card } from "../components/ui";

export function Guide() {
  const [active, setActive] = useState<GuideSlug>(GUIDES[0].slug);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 16 }}>
      <Card padding={8} style={{ alignSelf: "start" }}>
        {GUIDES.map((g) => {
          const isActive = g.slug === active;
          return (
            <button
              key={g.slug}
              onClick={() => setActive(g.slug)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "9px 10px",
                fontSize: 12.5,
                color: isActive ? "var(--text)" : "var(--text-2)",
                background: isActive ? "var(--card-2)" : "transparent",
                border: "1px solid",
                borderColor: isActive ? "var(--border)" : "transparent",
                borderRadius: 6,
                cursor: "pointer",
                marginBottom: 2,
              }}
            >
              {g.title}
            </button>
          );
        })}
      </Card>
      <Card padding={24}>
        <GuideContent slug={active} />
      </Card>
    </div>
  );
}

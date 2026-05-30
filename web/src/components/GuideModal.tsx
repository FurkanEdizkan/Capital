/**
 * In-app guides. A small registry maps a slug to a title + markdown body
 * (bundled from `src/guides/*.md`). `GuideButton` is a "?" trigger that opens
 * the matching guide in a modal; the Guide page lists them all.
 */
import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { I } from "./icons";
import { IconButton, Modal } from "./ui";

import aiProviders from "../guides/ai-providers.md?raw";
import binanceApiKey from "../guides/binance-api-key.md?raw";
import connections from "../guides/connections.md?raw";
import deployment from "../guides/deployment.md?raw";
import futures from "../guides/futures-trading.md?raw";
import news from "../guides/news.md?raw";

export type GuideSlug =
  | "binance-api-key"
  | "ai-providers"
  | "news"
  | "connections"
  | "futures-trading"
  | "deployment";

type Guide = { slug: GuideSlug; title: string; content: string };

export const GUIDES: Guide[] = [
  { slug: "binance-api-key", title: "Getting a Binance API key", content: binanceApiKey },
  { slug: "ai-providers", title: "Connecting an AI model", content: aiProviders },
  { slug: "news", title: "News", content: news },
  { slug: "connections", title: "Connections", content: connections },
  { slug: "futures-trading", title: "Futures & perpetuals", content: futures },
  { slug: "deployment", title: "Running Capital", content: deployment },
];

const BY_SLUG: Record<GuideSlug, Guide> = Object.fromEntries(
  GUIDES.map((g) => [g.slug, g]),
) as Record<GuideSlug, Guide>;

/** Renders guide markdown with the app's typography. */
export function GuideContent({ slug }: { slug: GuideSlug }) {
  return (
    <div className="guide-prose" style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text-2)" }}>
      <ReactMarkdown>{BY_SLUG[slug].content}</ReactMarkdown>
    </div>
  );
}

/** A small "?" help trigger that opens the matching guide in a modal. */
export function GuideButton({ slug, title }: { slug: GuideSlug; title?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <IconButton
        title={title ?? "Open guide"}
        onClick={() => setOpen(true)}
        style={{ width: 22, height: 22 }}
      >
        <I.Guide size={14} />
      </IconButton>
      <Modal open={open} onClose={() => setOpen(false)} title={BY_SLUG[slug].title}>
        <GuideContent slug={slug} />
      </Modal>
    </>
  );
}

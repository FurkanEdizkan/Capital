/**
 * Number formatting helpers — ported from the design bundle (data.jsx).
 * Numbers are the hero of this UI, so formatting lives in one place.
 */

export const fmt = (n: number, d = 2): string =>
  Number(n).toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });

export const fmtUsd = (n: number, d = 2): string => "$" + fmt(Math.abs(n), d);

export const fmtPct = (n: number, d = 2): string =>
  (n >= 0 ? "+" : "−") + fmt(Math.abs(n), d) + "%";

export const fmtSignedUsd = (n: number, d = 2): string =>
  (n >= 0 ? "+$" : "−$") + fmt(Math.abs(n), d);

export const fmtCompact = (n: number): string => {
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(2) + "K";
  return n.toFixed(2);
};

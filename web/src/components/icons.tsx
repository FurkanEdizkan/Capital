/**
 * Inline-SVG icon set — ported from the design bundle (icons.jsx).
 * Stroke-based, 16x16 viewBox, original (Lucide-style) artwork.
 */
import type { ReactNode, SVGProps } from "react";

type IconProps = Omit<SVGProps<SVGSVGElement>, "d" | "stroke"> & {
  d?: string | ReactNode;
  size?: number;
  stroke?: number;
};

export function Icon({ d, size = 16, stroke = 1.5, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {typeof d === "string" ? <path d={d} /> : d}
    </svg>
  );
}

type IconComponent = (p?: { size?: number; stroke?: number }) => ReactNode;

export const I: Record<string, IconComponent> = {
  Dashboard: (p) => (
    <Icon
      {...p}
      d={
        <>
          <rect x="1.5" y="1.5" width="5.5" height="6" rx="1" />
          <rect x="9" y="1.5" width="5.5" height="3.5" rx="1" />
          <rect x="1.5" y="9" width="5.5" height="5.5" rx="1" />
          <rect x="9" y="6.5" width="5.5" height="8" rx="1" />
        </>
      }
    />
  ),
  Markets: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M2 13 L6 8 L9 11 L14 4" />
          <path d="M10 4 L14 4 L14 8" />
        </>
      }
    />
  ),
  Strategies: (p) => (
    <Icon
      {...p}
      d={
        <>
          <circle cx="4" cy="4" r="2" />
          <circle cx="12" cy="4" r="2" />
          <circle cx="8" cy="12" r="2" />
          <path d="M5.4 5.4 L6.6 10.6" />
          <path d="M10.6 5.4 L9.4 10.6" />
          <path d="M6 4 L10 4" />
        </>
      }
    />
  ),
  Backtest: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M2 14 L2 2 L14 2" />
          <path d="M5 11 L7 8 L9 10 L13 5" />
          <circle cx="13" cy="5" r="1" />
        </>
      }
    />
  ),
  History: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M2 7 A6 6 0 1 1 4 12.2" />
          <path d="M2 3 L2 7 L6 7" />
          <path d="M8 5 L8 8 L10.5 9.5" />
        </>
      }
    />
  ),
  Settings: (p) => (
    <Icon
      {...p}
      d={
        <>
          <circle cx="8" cy="8" r="2" />
          <path d="M8 1.5 L8 3 M8 13 L8 14.5 M1.5 8 L3 8 M13 8 L14.5 8 M3.3 3.3 L4.4 4.4 M11.6 11.6 L12.7 12.7 M3.3 12.7 L4.4 11.6 M11.6 4.4 L12.7 3.3" />
        </>
      }
    />
  ),
  Users: (p) => (
    <Icon
      {...p}
      d={
        <>
          <circle cx="6" cy="5.5" r="2.5" />
          <path d="M1.5 13.5 C1.5 11 3.5 9.5 6 9.5 C8.5 9.5 10.5 11 10.5 13.5" />
          <circle cx="11.5" cy="6" r="2" />
          <path d="M11 9.5 C13 9.5 14.5 11 14.5 13" />
        </>
      }
    />
  ),
  Search: (p) => (
    <Icon
      {...p}
      d={
        <>
          <circle cx="7" cy="7" r="4.5" />
          <path d="M10.5 10.5 L14 14" />
        </>
      }
    />
  ),
  Bell: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M4 7 A4 4 0 0 1 12 7 L12 10 L13 12 L3 12 L4 10 Z" />
          <path d="M6.5 12 A1.5 1.5 0 0 0 9.5 12" />
        </>
      }
    />
  ),
  Chevron: (p) => <Icon {...p} d="M5 4 L9 8 L5 12" />,
  ChevronDown: (p) => <Icon {...p} d="M4 6 L8 10 L12 6" />,
  Plus: (p) => <Icon {...p} d="M8 3 L8 13 M3 8 L13 8" />,
  Close: (p) => <Icon {...p} d="M4 4 L12 12 M12 4 L4 12" />,
  Play: (p) => <Icon {...p} d="M4 3 L13 8 L4 13 Z" />,
  Kill: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M8 1.5 L8 8" />
          <path d="M3.5 4.5 A5.5 5.5 0 1 0 12.5 4.5" />
        </>
      }
    />
  ),
  Eye: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M1.5 8 C3 4.5 5.5 3 8 3 C10.5 3 13 4.5 14.5 8 C13 11.5 10.5 13 8 13 C5.5 13 3 11.5 1.5 8 Z" />
          <circle cx="8" cy="8" r="2" />
        </>
      }
    />
  ),
  EyeOff: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M2 8 C3 6 4.5 4.5 6 3.8" />
          <path d="M10 3.8 C12 4.5 13.5 6 14.5 8 C13.5 10 12 11.5 10 12.2" />
          <path d="M2 14 L14 2" />
        </>
      }
    />
  ),
  ArrowUp: (p) => <Icon {...p} d="M8 13 L8 3 M4 7 L8 3 L12 7" />,
  ArrowDown: (p) => <Icon {...p} d="M8 3 L8 13 M4 9 L8 13 L12 9" />,
  Check: (p) => <Icon {...p} d="M3 8.5 L6.5 12 L13 5" />,
  Info: (p) => (
    <Icon
      {...p}
      d={
        <>
          <circle cx="8" cy="8" r="6" />
          <path d="M8 7 L8 11 M8 5 L8 5.5" />
        </>
      }
    />
  ),
  Warn: (p) => (
    <Icon
      {...p}
      d={
        <>
          <path d="M8 1.5 L15 13.5 L1 13.5 Z" />
          <path d="M8 6 L8 10 M8 11.5 L8 12" />
        </>
      }
    />
  ),
};

/** Brand mark — a "C" with a bolt motif. */
export function BrandMark({
  size = 22,
  color = "#10B981",
}: {
  size?: number;
  color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden>
      <rect x="1" y="1" width="26" height="26" rx="7" fill="#0E0E12" stroke="#27272A" />
      <path
        d="M19.4 9.2 A6.5 6.5 0 1 0 19.4 18.8"
        stroke={color}
        strokeWidth="2.3"
        strokeLinecap="round"
      />
      <path d="M14.5 9.5 L11.5 14 L14 14 L13 18.5 L17 13.5 L14.5 13.5 Z" fill={color} />
    </svg>
  );
}

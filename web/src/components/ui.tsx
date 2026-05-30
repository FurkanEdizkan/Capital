/**
 * Shared UI primitives — ported from the design bundle (ui.jsx) to typed React.
 * This is Capital's design system: a hand-built, shadcn-style component set
 * tuned for a dark, data-dense trading terminal. Every screen builds on these.
 */
import {
  useState,
  type ChangeEvent,
  type CSSProperties,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { I } from "./icons";
import { fmt } from "../lib/format";

const uiBoxStyle: CSSProperties = {
  background: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
};

/* ---------------------------------------------------------------- Card --- */

export function Card({
  children,
  padding = 0,
  style,
  className,
}: {
  children?: ReactNode;
  padding?: number | string;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <div className={className} style={{ ...uiBoxStyle, padding, ...style }}>
      {children}
    </div>
  );
}

export function SectionHeader({
  title,
  subtitle,
  right,
  style,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        padding: "14px 16px",
        borderBottom: "1px solid var(--border-soft)",
        ...style,
      }}
    >
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{title}</div>
        {subtitle && (
          <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 2 }}>{subtitle}</div>
        )}
      </div>
      {right}
    </div>
  );
}

/* --------------------------------------------------------------- Badge --- */

export type BadgeTone = "muted" | "green" | "red" | "amber" | "blue" | "violet" | "live";

export function Badge({
  children,
  tone = "muted",
  variant = "soft",
  size = "sm",
  style,
}: {
  children?: ReactNode;
  tone?: BadgeTone;
  variant?: "soft" | "solid" | "outline";
  size?: "sm" | "lg";
  style?: CSSProperties;
}) {
  const tones: Record<BadgeTone, { fg: string; bg: string; bd: string }> = {
    muted: { fg: "var(--text-2)", bg: "rgba(255,255,255,.04)", bd: "var(--border)" },
    green: { fg: "#34D399", bg: "var(--green-bg)", bd: "rgba(16,185,129,.30)" },
    red: { fg: "#F87171", bg: "var(--red-bg)", bd: "rgba(239,68,68,.30)" },
    // amber/blue/violet neutralised — the theme is monochrome apart from
    // green/red. They remain distinct grey tones for non-semantic labels.
    amber: { fg: "var(--text)", bg: "var(--amber-bg)", bd: "var(--border)" },
    blue: { fg: "var(--text-2)", bg: "var(--blue-bg)", bd: "var(--border)" },
    violet: { fg: "var(--text-3)", bg: "var(--violet-bg)", bd: "var(--border)" },
    live: { fg: "#FCA5A5", bg: "rgba(239,68,68,.14)", bd: "rgba(239,68,68,.45)" },
  };
  const t = tones[tone] ?? tones.muted;
  const isOutline = variant === "outline";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: size === "lg" ? 11.5 : 10.5,
        fontWeight: 600,
        letterSpacing: ".02em",
        textTransform: "uppercase",
        color: t.fg,
        background: isOutline ? "transparent" : t.bg,
        border: `1px solid ${t.bd}`,
        borderRadius: 4,
        padding: size === "lg" ? "3px 8px" : "2px 6px",
        lineHeight: 1.1,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

export function Pill({ children, style }: { children?: ReactNode; style?: CSSProperties }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 11,
        fontWeight: 500,
        color: "var(--text-2)",
        background: "rgba(255,255,255,.03)",
        border: "1px solid var(--border)",
        borderRadius: 999,
        padding: "2px 8px",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/* -------------------------------------------------------------- Button --- */

export type ButtonKind = "default" | "ghost" | "outline" | "primary" | "danger" | "soft";

export function Button({
  children,
  kind = "default",
  size = "md",
  icon,
  iconRight,
  full,
  onClick,
  style,
  type = "button",
  disabled,
}: {
  children?: ReactNode;
  kind?: ButtonKind;
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  iconRight?: ReactNode;
  full?: boolean;
  onClick?: () => void;
  style?: CSSProperties;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
}) {
  const sizes = {
    sm: { h: 26, px: 10, fs: 12, gap: 6 },
    md: { h: 32, px: 12, fs: 12.5, gap: 6 },
    lg: { h: 38, px: 16, fs: 13, gap: 8 },
  }[size];
  const kinds: Record<ButtonKind, { bg: string; bd: string; fg: string; hover: string }> = {
    default: { bg: "var(--card-2)", bd: "var(--border)", fg: "var(--text)", hover: "#1F1F22" },
    ghost: { bg: "transparent", bd: "transparent", fg: "var(--text-2)", hover: "#1B1B1F" },
    outline: { bg: "transparent", bd: "var(--border)", fg: "var(--text)", hover: "#1B1B1F" },
    primary: { bg: "#10B981", bd: "#10B981", fg: "#02261C", hover: "#34D399" },
    danger: { bg: "#DC2626", bd: "#DC2626", fg: "#fff", hover: "#EF4444" },
    soft: {
      bg: "rgba(16,185,129,.10)",
      bd: "rgba(16,185,129,.30)",
      fg: "#34D399",
      hover: "rgba(16,185,129,.15)",
    },
  };
  const k = kinds[kind];
  const [hover, setHover] = useState(false);
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: sizes.gap,
        height: sizes.h,
        padding: `0 ${sizes.px}px`,
        fontSize: sizes.fs,
        fontWeight: 500,
        color: k.fg,
        background: hover && !disabled ? k.hover : k.bg,
        border: `1px solid ${k.bd}`,
        borderRadius: 6,
        width: full ? "100%" : "auto",
        transition: "background 120ms ease, border-color 120ms ease, color 120ms ease",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        ...style,
      }}
    >
      {icon}
      {children}
      {iconRight}
    </button>
  );
}

export function IconButton({
  children,
  onClick,
  style,
  title,
}: {
  children?: ReactNode;
  onClick?: () => void;
  style?: CSSProperties;
  title?: string;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      title={title}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 28,
        height: 28,
        background: hover ? "#1F1F22" : "transparent",
        color: hover ? "var(--text)" : "var(--text-2)",
        border: "1px solid transparent",
        borderRadius: 6,
        cursor: "pointer",
        transition: "all 120ms",
        ...style,
      }}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------------- Input --- */

export function Input({
  value,
  onChange,
  placeholder,
  prefix,
  suffix,
  type = "text",
  size = "md",
  style,
  full,
  ...rest
}: {
  value?: string;
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  prefix?: ReactNode;
  suffix?: ReactNode;
  type?: string;
  size?: "sm" | "md" | "lg";
  style?: CSSProperties;
  full?: boolean;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "size" | "prefix" | "value" | "onChange">) {
  const sizes = { sm: 28, md: 34, lg: 38 };
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: sizes[size],
        padding: "0 10px",
        background: "var(--card-2)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        width: full ? "100%" : "auto",
        transition: "border-color 120ms",
        ...style,
      }}
    >
      {prefix && (
        <span style={{ color: "var(--text-3)", display: "inline-flex" }}>{prefix}</span>
      )}
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        {...rest}
        style={{
          flex: 1,
          minWidth: 0,
          background: "transparent",
          border: "none",
          outline: "none",
          color: "var(--text)",
          fontSize: 13,
          width: "100%",
        }}
      />
      {suffix && <span style={{ color: "var(--text-3)" }}>{suffix}</span>}
    </div>
  );
}

/* -------------------------------------------------------------- Toggle --- */

export function Toggle({
  checked,
  onChange,
  size = "md",
  label,
}: {
  checked: boolean;
  onChange?: (v: boolean) => void;
  size?: "sm" | "md";
  label?: ReactNode;
}) {
  const w = size === "sm" ? 28 : 34;
  const h = size === "sm" ? 16 : 20;
  const knob = h - 4;
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
      <span
        onClick={() => onChange?.(!checked)}
        style={{
          position: "relative",
          width: w,
          height: h,
          background: checked ? "#10B981" : "#27272A",
          borderRadius: 999,
          transition: "background 140ms ease",
          flex: "0 0 auto",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? w - knob - 2 : 2,
            width: knob,
            height: knob,
            background: "#fff",
            borderRadius: "50%",
            transition: "left 140ms ease",
            boxShadow: "0 1px 2px rgba(0,0,0,.4)",
          }}
        />
      </span>
      {label && <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>{label}</span>}
    </label>
  );
}

/* ---------------------------------------------------------------- Tabs --- */

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  style,
}: {
  tabs: { id: T; label: ReactNode }[];
  active: T;
  onChange: (id: T) => void;
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: "flex", gap: 4, ...style }}>
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            style={{
              padding: "6px 12px",
              fontSize: 12.5,
              fontWeight: 500,
              color: isActive ? "var(--text)" : "var(--text-3)",
              background: isActive ? "var(--card-2)" : "transparent",
              border: "1px solid",
              borderColor: isActive ? "var(--border)" : "transparent",
              borderRadius: 6,
              cursor: "pointer",
              transition: "all 120ms",
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = "md",
}: {
  options: { value: T; label: ReactNode }[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  const h = size === "sm" ? 26 : 32;
  return (
    <div
      style={{
        display: "inline-flex",
        background: "var(--card-2)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: 3,
        gap: 2,
        height: h,
      }}
    >
      {options.map((o) => {
        const isActive = o.value === value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            style={{
              padding: "0 10px",
              fontSize: 12,
              fontWeight: 500,
              color: isActive ? "var(--text)" : "var(--text-3)",
              background: isActive ? "var(--elev)" : "transparent",
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
              transition: "all 100ms",
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------ StatTile --- */

export function StatTile({
  label,
  value,
  sub,
  subTone = "muted",
  trend,
  accent,
  icon,
  big = false,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  subTone?: "green" | "red" | "amber" | "blue" | "muted";
  trend?: "up" | "down";
  accent?: string;
  icon?: ReactNode;
  big?: boolean;
}) {
  const tones = {
    green: "#34D399",
    red: "#F87171",
    amber: "#FBBF24",
    blue: "#60A5FA",
    muted: "var(--text-3)",
  };
  return (
    <div
      style={{
        ...uiBoxStyle,
        padding: big ? "18px 20px" : "16px 18px",
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {accent && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: accent,
            opacity: 0.7,
          }}
        />
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <span
          style={{
            fontSize: 11.5,
            fontWeight: 500,
            color: "var(--text-3)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </span>
        {icon && <span style={{ color: "var(--text-4)" }}>{icon}</span>}
      </div>
      <div
        className="num"
        style={{
          fontSize: big ? 28 : 24,
          fontWeight: 600,
          color: "var(--text)",
          marginTop: 6,
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub && (
        <div
          className="num"
          style={{
            fontSize: 12,
            color: tones[subTone] ?? tones.muted,
            marginTop: 6,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {trend === "up" && (
            <span
              style={{
                display: "inline-block",
                width: 0,
                height: 0,
                borderLeft: "4px solid transparent",
                borderRight: "4px solid transparent",
                borderBottom: "5px solid currentColor",
              }}
            />
          )}
          {trend === "down" && (
            <span
              style={{
                display: "inline-block",
                width: 0,
                height: 0,
                borderLeft: "4px solid transparent",
                borderRight: "4px solid transparent",
                borderTop: "5px solid currentColor",
              }}
            />
          )}
          {sub}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------- Modal/Drawer --- */

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  width = 560,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  if (!open) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 80,
        background: "rgba(4,4,6,.66)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          width,
          maxWidth: "100%",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 50px rgba(0,0,0,.5)",
        }}
      >
        {title && (
          <div
            style={{
              padding: "14px 18px",
              borderBottom: "1px solid var(--border-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
            <IconButton onClick={onClose}>
              <I.Close />
            </IconButton>
          </div>
        )}
        <div style={{ padding: 18, overflowY: "auto", flex: 1 }}>{children}</div>
        {footer && (
          <div
            style={{
              padding: "12px 18px",
              borderTop: "1px solid var(--border-soft)",
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 480,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  subtitle?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  return (
    <>
      {open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 70,
            background: "rgba(4,4,6,.55)",
            backdropFilter: "blur(2px)",
          }}
          onClick={onClose}
        />
      )}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width,
          maxWidth: "92vw",
          background: "var(--card)",
          borderLeft: "1px solid var(--border)",
          transform: open ? "translateX(0)" : "translateX(110%)",
          transition: "transform 260ms cubic-bezier(.2,.8,.2,1)",
          zIndex: 71,
          display: "flex",
          flexDirection: "column",
          boxShadow: "-12px 0 30px rgba(0,0,0,.4)",
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-soft)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text)" }}>{title}</div>
            {subtitle && (
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>{subtitle}</div>
            )}
          </div>
          <IconButton onClick={onClose}>
            <I.Close />
          </IconButton>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>{children}</div>
        {footer && (
          <div
            style={{
              padding: "12px 20px",
              borderTop: "1px solid var(--border-soft)",
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </>
  );
}

/* ----------------------------------------------------------- DataTable --- */

export type Column<R> = {
  key: string;
  label: ReactNode;
  align?: "left" | "right" | "center";
  width?: number | string;
  sortable?: boolean;
  wrap?: boolean;
  render?: (row: R, i: number) => ReactNode;
};

export type Sort = { key: string; dir: "asc" | "desc" };

export function DataTable<R extends Record<string, unknown>>({
  columns,
  rows,
  sort,
  onSort,
  rowKey,
  dense = false,
  sticky = true,
  onRowClick,
  highlightRow,
}: {
  columns: Column<R>[];
  rows: R[];
  sort?: Sort;
  onSort?: (key: string) => void;
  rowKey?: (row: R, i: number) => string | number;
  dense?: boolean;
  sticky?: boolean;
  onRowClick?: (row: R) => void;
  highlightRow?: (row: R, i: number) => boolean;
}) {
  const cellPad = dense ? "8px 12px" : "12px 14px";
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0, minWidth: 700 }}
      >
        <thead>
          <tr>
            {columns.map((col) => {
              const isSortable = col.sortable !== false && !!onSort;
              const isActive = sort && sort.key === col.key;
              return (
                <th
                  key={col.key}
                  style={{
                    textAlign: col.align ?? "left",
                    padding: cellPad,
                    fontSize: 11,
                    fontWeight: 500,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    color: "var(--text-3)",
                    borderBottom: "1px solid var(--border-soft)",
                    background: sticky ? "var(--card)" : "transparent",
                    position: sticky ? "sticky" : "static",
                    top: 0,
                    whiteSpace: "nowrap",
                    width: col.width,
                    cursor: isSortable ? "pointer" : "default",
                    userSelect: "none",
                  }}
                  onClick={isSortable ? () => onSort?.(col.key) : undefined}
                >
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      justifyContent: col.align === "right" ? "flex-end" : "flex-start",
                    }}
                  >
                    {col.label}
                    {isActive &&
                      (sort.dir === "asc" ? (
                        <I.ArrowUp size={10} stroke={2} />
                      ) : (
                        <I.ArrowDown size={10} stroke={2} />
                      ))}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const k = rowKey ? rowKey(row, i) : i;
            const isHi = highlightRow && highlightRow(row, i);
            return (
              <tr
                key={k}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={{
                  cursor: onRowClick ? "pointer" : "default",
                  background: isHi ? "rgba(16,185,129,.05)" : "transparent",
                  transition: "background 100ms",
                }}
                onMouseEnter={(e) => {
                  if (onRowClick) e.currentTarget.style.background = "rgba(255,255,255,.025)";
                }}
                onMouseLeave={(e) => {
                  if (onRowClick)
                    e.currentTarget.style.background = isHi
                      ? "rgba(16,185,129,.05)"
                      : "transparent";
                }}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    style={{
                      padding: cellPad,
                      textAlign: col.align ?? "left",
                      fontSize: 12.5,
                      color: "var(--text)",
                      borderBottom: "1px solid var(--border-soft)",
                      whiteSpace: col.wrap ? "normal" : "nowrap",
                    }}
                  >
                    {col.render ? col.render(row, i) : (row[col.key] as ReactNode)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)", fontSize: 13 }}>
          No rows.
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------- Number display --- */

export function Money({
  value,
  signed = false,
  prefix = "$",
  decimals = 2,
  style,
  neutralZero = false,
}: {
  value: number;
  signed?: boolean;
  prefix?: string;
  decimals?: number;
  style?: CSSProperties;
  neutralZero?: boolean;
}) {
  const isPos = value > 0;
  const isNeg = value < 0;
  const color =
    neutralZero && value === 0
      ? "var(--text)"
      : isPos
        ? "#34D399"
        : isNeg
          ? "#F87171"
          : "var(--text)";
  const sign = signed ? (isPos ? "+" : isNeg ? "−" : "") : "";
  return (
    <span className="num" style={{ color, fontVariantNumeric: "tabular-nums", ...style }}>
      {sign}
      {prefix}
      {fmt(Math.abs(value), decimals)}
    </span>
  );
}

export function Pct({
  value,
  decimals = 2,
  style,
}: {
  value: number;
  decimals?: number;
  style?: CSSProperties;
}) {
  const isPos = value > 0;
  const isNeg = value < 0;
  const color = isPos ? "#34D399" : isNeg ? "#F87171" : "var(--text-2)";
  const sign = isPos ? "+" : isNeg ? "−" : "";
  return (
    <span className="num" style={{ color, ...style }}>
      {sign}
      {fmt(Math.abs(value), decimals)}%
    </span>
  );
}

const SYMBOL_COLORS: Record<string, string> = {
  BTC: "#F7931A",
  ETH: "#627EEA",
  SOL: "#9945FF",
  BNB: "#F3BA2F",
  XRP: "#23292F",
  AVAX: "#E84142",
  LINK: "#2A5ADA",
  ARB: "#28A0F0",
  DOGE: "#C2A633",
  MATIC: "#8247E5",
  ATOM: "#5064FB",
  OP: "#FF0420",
  INJ: "#00F0BB",
  SUI: "#4DA2FF",
  APT: "#00BFA5",
};

export function SymbolCell({ sym }: { sym: string }) {
  const base = sym.replace("USDT", "");
  const bg = SYMBOL_COLORS[base] ?? "#3F3F46";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 9 }}>
      <span
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          background: bg + "22",
          color: bg,
          border: "1px solid " + bg + "44",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 9.5,
          fontWeight: 700,
          letterSpacing: ".02em",
        }}
      >
        {base.slice(0, 3)}
      </span>
      <span style={{ fontWeight: 500 }}>
        {base}
        <span style={{ color: "var(--text-4)" }}>/USDT</span>
      </span>
    </span>
  );
}

export function SideBadge({ side }: { side: string }) {
  const isLong = side === "long" || side === "buy";
  return <Badge tone={isLong ? "green" : "red"}>{isLong ? "Long" : "Short"}</Badge>;
}

export function BuySellBadge({ side }: { side: "buy" | "sell" }) {
  return (
    <Badge tone={side === "buy" ? "green" : "red"} variant="soft">
      {side}
    </Badge>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: "50%",
          background: "var(--card-2)",
          border: "1px solid var(--border)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-3)",
          marginBottom: 12,
        }}
      >
        {icon}
      </div>
      <div style={{ color: "var(--text)", fontWeight: 600, fontSize: 13.5 }}>{title}</div>
      {body && (
        <div style={{ fontSize: 12.5, marginTop: 4, maxWidth: 320, marginInline: "auto" }}>
          {body}
        </div>
      )}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function Kbd({ children }: { children?: ReactNode }) {
  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: "var(--mono)",
        fontSize: 10.5,
        padding: "1px 5px",
        borderRadius: 4,
        background: "var(--card-2)",
        border: "1px solid var(--border)",
        color: "var(--text-2)",
        lineHeight: 1.4,
      }}
    >
      {children}
    </span>
  );
}

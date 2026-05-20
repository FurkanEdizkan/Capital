/**
 * App shell — collapsible sidebar + top bar — ported from the design bundle
 * (shell.jsx) and adapted to react-router (screen state → routes).
 */
import { useEffect, useState, type ReactNode } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { BrandMark, I } from "../icons";
import { Badge, IconButton, Input, Kbd } from "../ui";
import { useAuth } from "../../lib/auth";
import { NAV, type NavItem } from "./nav";

export type TradingMode = "SIM" | "TESTNET" | "LIVE";

/* -------------------------------------------------------------- Sidebar --- */

function Sidebar({
  items,
  activeId,
  collapsed,
  onToggleCollapsed,
}: {
  items: NavItem[];
  activeId: string;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const navigate = useNavigate();
  const w = collapsed ? 64 : 224;
  return (
    <aside
      style={{
        width: w,
        flex: `0 0 ${w}px`,
        borderRight: "1px solid var(--border)",
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        transition: "width 180ms cubic-bezier(.2,.8,.2,1), flex-basis 180ms cubic-bezier(.2,.8,.2,1)",
        position: "sticky",
        top: 0,
        height: "100vh",
      }}
    >
      <div
        style={{
          height: 56,
          padding: collapsed ? "0 16px" : "0 18px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <BrandMark size={26} />
        {!collapsed && (
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
            <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-.01em" }}>Capital</span>
            <span style={{ fontSize: 10.5, color: "var(--text-3)", fontFamily: "var(--mono)" }}>
              v0.1.0
            </span>
          </div>
        )}
      </div>

      <nav
        style={{
          padding: collapsed ? "10px 8px" : "10px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 1,
        }}
      >
        {!collapsed && (
          <div
            style={{
              fontSize: 10.5,
              color: "var(--text-4)",
              textTransform: "uppercase",
              letterSpacing: ".08em",
              padding: "10px 8px 6px",
            }}
          >
            Engine
          </div>
        )}
        {items.map((item) => {
          const isActive = item.id === activeId;
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.path)}
              title={collapsed ? item.label : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: collapsed ? "9px 0" : "8px 10px",
                width: "100%",
                background: isActive ? "rgba(255,255,255,.04)" : "transparent",
                color: isActive ? "var(--text)" : "var(--text-2)",
                border: "1px solid",
                borderColor: isActive ? "var(--border)" : "transparent",
                borderRadius: 6,
                cursor: "pointer",
                justifyContent: collapsed ? "center" : "flex-start",
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                transition: "background 100ms, color 100ms",
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,.025)";
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = "transparent";
              }}
            >
              <span
                style={{
                  color: isActive ? "#34D399" : "var(--text-3)",
                  display: "inline-flex",
                }}
              >
                <item.icon />
              </span>
              {!collapsed && <span style={{ flex: 1, textAlign: "left" }}>{item.label}</span>}
              {!collapsed && item.badge && (
                <span
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 10.5,
                    color: "var(--text-3)",
                    background: "var(--card-2)",
                    border: "1px solid var(--border)",
                    padding: "0 5px",
                    borderRadius: 4,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      {!collapsed && (
        <div
          style={{
            padding: "12px 14px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 11,
              color: "var(--text-3)",
            }}
          >
            <span style={{ fontFamily: "var(--mono)", letterSpacing: ".02em" }}>ENGINE STATUS</span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                color: "var(--text-4)",
              }}
            >
              <span
                style={{ width: 6, height: 6, borderRadius: 999, background: "var(--text-4)" }}
              />
              Offline
            </span>
          </div>
          <div style={{ fontSize: 10.5, color: "var(--text-4)", lineHeight: 1.5 }}>
            Trading engine not yet connected — UI runs on mock data until the
            engine ships.
          </div>
        </div>
      )}

      <button
        onClick={onToggleCollapsed}
        title={collapsed ? "Expand" : "Collapse"}
        style={{
          height: 36,
          background: "transparent",
          color: "var(--text-3)",
          border: "none",
          borderTop: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          padding: collapsed ? 0 : "0 14px",
          fontSize: 12,
          cursor: "pointer",
        }}
      >
        {!collapsed && <span>Collapse</span>}
        <span
          style={{
            transform: collapsed ? "rotate(0deg)" : "rotate(180deg)",
            transition: "transform 180ms",
          }}
        >
          <I.Chevron />
        </span>
      </button>
    </aside>
  );
}

/* ------------------------------------------------------------- TopBar --- */

function ModeBadge({ mode }: { mode: TradingMode }) {
  if (mode === "LIVE") {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          padding: "4px 9px",
          borderRadius: 5,
          background: "rgba(239,68,68,.14)",
          border: "1px solid rgba(239,68,68,.45)",
          color: "#FCA5A5",
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".10em",
          textTransform: "uppercase",
        }}
      >
        <span
          className="pulse-red"
          style={{ width: 6, height: 6, borderRadius: 999, background: "#EF4444" }}
        />
        Live Trading
      </span>
    );
  }
  if (mode === "TESTNET") {
    return (
      <Badge tone="amber" variant="outline" size="lg" style={{ padding: "4px 9px" }}>
        Testnet
      </Badge>
    );
  }
  return (
    <Badge tone="blue" variant="outline" size="lg" style={{ padding: "4px 9px" }}>
      Simulation
    </Badge>
  );
}

function ConnectionStatus({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        fontSize: 12,
        color: "var(--text-2)",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: 999,
          background: ok ? "#10B981" : "var(--text-4)",
          boxShadow: ok ? "0 0 8px rgba(16,185,129,.7)" : "none",
        }}
      />
      <span style={{ fontFamily: "var(--mono)" }}>Engine</span>
      <span style={{ color: "var(--text-3)", fontFamily: "var(--mono)" }}>
        {ok ? "online" : "offline"}
      </span>
    </span>
  );
}

function KillSwitch({
  armed,
  onArm,
  onKill,
}: {
  armed: boolean;
  onArm: () => void;
  onKill: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={armed ? onKill : onArm}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={armed ? "Click again to confirm halt" : "Halt engine immediately"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        height: 32,
        padding: "0 12px",
        background: armed ? "#DC2626" : hover ? "rgba(239,68,68,.10)" : "transparent",
        border: armed ? "1px solid #EF4444" : "1px solid rgba(239,68,68,.45)",
        color: armed ? "#fff" : "#F87171",
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: ".04em",
        cursor: "pointer",
        textTransform: "uppercase",
        transition: "all 120ms",
      }}
    >
      <I.Kill size={14} stroke={armed ? 2.2 : 1.8} />
      {armed ? "Confirm halt" : "Kill switch"}
    </button>
  );
}

function UserMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const initials = (user?.username ?? "??").slice(0, 2).toUpperCase();
  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 8px 4px 4px",
          background: "transparent",
          border: "1px solid transparent",
          borderRadius: 6,
          cursor: "pointer",
          color: "var(--text)",
        }}
      >
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            background: "linear-gradient(135deg,#10B981,#0EA5E9)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            fontWeight: 700,
            color: "#02261C",
          }}
        >
          {initials}
        </span>
        <span
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            lineHeight: 1.1,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 500 }}>{user?.username}</span>
          <span style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "capitalize" }}>
            {user?.role}
          </span>
        </span>
        <span style={{ color: "var(--text-3)", marginLeft: 2 }}>
          <I.ChevronDown size={12} />
        </span>
      </button>
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setOpen(false)} />
          <div
            style={{
              position: "absolute",
              right: 0,
              top: 40,
              zIndex: 41,
              minWidth: 160,
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 4,
              boxShadow: "0 12px 30px rgba(0,0,0,.5)",
            }}
          >
            <button
              onClick={signOut}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                background: "transparent",
                border: "none",
                borderRadius: 6,
                color: "var(--text-2)",
                fontSize: 12.5,
                cursor: "pointer",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--card-2)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function TopBar({
  item,
  mode,
  killArmed,
  onArmKill,
  onKill,
}: {
  item: NavItem | undefined;
  mode: TradingMode;
  killArmed: boolean;
  onArmKill: () => void;
  onKill: () => void;
}) {
  return (
    <header
      style={{
        height: 56,
        flex: "0 0 56px",
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        gap: 16,
        position: "sticky",
        top: 0,
        zIndex: 30,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
          {item?.title ?? "Capital"}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 1 }}>
          {item?.subtitle ?? ""}
        </div>
      </div>

      <div style={{ flex: 1 }} />

      <Input
        prefix={<I.Search />}
        placeholder="Search symbols, strategies, trades…"
        size="sm"
        style={{ width: 360, height: 32 }}
        suffix={<Kbd>⌘K</Kbd>}
      />

      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <ConnectionStatus ok={false} />
        <div style={{ width: 1, height: 24, background: "var(--border)" }} />
        <ModeBadge mode={mode} />
        <KillSwitch armed={killArmed} onArm={onArmKill} onKill={onKill} />
        <div style={{ width: 1, height: 24, background: "var(--border)" }} />
        <IconButton title="Notifications">
          <I.Bell />
        </IconButton>
        <UserMenu />
      </div>
    </header>
  );
}

/* --------------------------------------------------------------- Shell --- */

export function Shell() {
  const { user } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [killArmed, setKillArmed] = useState(false);
  const [killToast, setKillToast] = useState(false);
  const mode: TradingMode = "SIM";

  const items = NAV.filter((n) => !n.adminOnly || user?.role === "admin");
  const active =
    [...items].sort((a, b) => b.path.length - a.path.length).find((n) =>
      n.path === "/" ? location.pathname === "/" : location.pathname.startsWith(n.path),
    ) ?? items[0];

  useEffect(() => {
    if (!killArmed) return;
    const t = setTimeout(() => setKillArmed(false), 4000);
    return () => clearTimeout(t);
  }, [killArmed]);

  const handleKill = () => {
    setKillArmed(false);
    setKillToast(true);
    setTimeout(() => setKillToast(false), 3500);
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg)" }}>
      <Sidebar
        items={items}
        activeId={active?.id ?? ""}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
      />
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <TopBar
          item={active}
          mode={mode}
          killArmed={killArmed}
          onArmKill={() => setKillArmed(true)}
          onKill={handleKill}
        />
        <div style={{ padding: "20px 24px 40px", flex: 1, minWidth: 0 }}>
          <Outlet />
        </div>
      </main>

      {killToast && (
        <ToastHalt />
      )}
    </div>
  );
}

function ToastHalt(): ReactNode {
  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        zIndex: 90,
        background: "var(--card)",
        border: "1px solid rgba(239,68,68,.5)",
        borderRadius: 8,
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        boxShadow: "0 12px 30px rgba(0,0,0,.5)",
        minWidth: 280,
      }}
    >
      <span
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          background: "rgba(239,68,68,.15)",
          color: "#F87171",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <I.Kill size={16} stroke={2} />
      </span>
      <div>
        <div style={{ fontWeight: 600, fontSize: 13 }}>Engine halt requested</div>
        <div style={{ fontSize: 11.5, color: "var(--text-3)" }}>
          Wired to the engine in a later phase
        </div>
      </div>
    </div>
  );
}

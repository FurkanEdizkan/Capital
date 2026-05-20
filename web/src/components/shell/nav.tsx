/** Sidebar / route configuration for the app shell. */
import type { ReactNode } from "react";
import { I } from "../icons";

export type NavItem = {
  id: string;
  label: string;
  path: string;
  icon: (p?: { size?: number; stroke?: number }) => ReactNode;
  badge?: string;
  /** Only visible to admins (Settings, Users) — see plan: Authentication & Roles. */
  adminOnly?: boolean;
  /** Topbar title + subtitle. */
  title: string;
  subtitle: string;
};

export const NAV: NavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    path: "/",
    icon: I.Dashboard,
    title: "Dashboard",
    subtitle: "Live engine state",
  },
  {
    id: "markets",
    label: "Markets",
    path: "/markets",
    icon: I.Markets,
    title: "Markets",
    subtitle: "Spot pairs & perpetuals",
  },
  {
    id: "strategies",
    label: "Strategies",
    path: "/strategies",
    icon: I.Strategies,
    badge: "6",
    title: "Strategies",
    subtitle: "Automated trading strategies",
  },
  {
    id: "backtest",
    label: "Backtest",
    path: "/backtest",
    icon: I.Backtest,
    title: "Backtest",
    subtitle: "Historical simulation",
  },
  {
    id: "history",
    label: "History",
    path: "/history",
    icon: I.History,
    title: "History",
    subtitle: "Transaction log & engine events",
  },
  {
    id: "settings",
    label: "Settings",
    path: "/settings",
    icon: I.Settings,
    adminOnly: true,
    title: "Settings",
    subtitle: "API, risk limits, providers",
  },
  {
    id: "users",
    label: "Users",
    path: "/users",
    icon: I.Users,
    adminOnly: true,
    title: "Users",
    subtitle: "Operators with engine access",
  },
];

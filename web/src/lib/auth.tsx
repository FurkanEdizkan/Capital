/**
 * Authentication context + protected-route wrapper.
 *
 * Talks to the real engine: `signIn` posts to `/api/auth/login` (OAuth2
 * password form), stores the JWT pair, and the access token is attached to
 * every API request by the client middleware. The session is restored on
 * load by validating the stored token against `/api/auth/me`.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, setAuthToken } from "./api/client";

export type Role = "admin" | "user";
export type User = { username: string; role: Role };

type Tokens = { access_token: string; refresh_token: string };

type AuthState = {
  user: User | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
};

const STORAGE_KEY = "capital.auth";
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const AuthContext = createContext<AuthState | null>(null);

function loadTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

function saveTokens(t: Tokens): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
}

function clearTokens(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** POST the OAuth2 password form to the engine. */
async function postLogin(username: string, password: string): Promise<Tokens> {
  const resp = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => null);
    throw new Error(detail?.detail ?? "Login failed");
  }
  return (await resp.json()) as Tokens;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session on load: apply the stored token, validate via /me.
  useEffect(() => {
    const tokens = loadTokens();
    if (!tokens) {
      setLoading(false);
      return;
    }
    setAuthToken(tokens.access_token);
    api
      .GET("/api/auth/me")
      .then(({ data }) => {
        if (data) {
          setUser({ username: data.username, role: data.role as Role });
        } else {
          clearTokens();
          setAuthToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const tokens = await postLogin(username, password);
    saveTokens(tokens);
    setAuthToken(tokens.access_token);
    const { data } = await api.GET("/api/auth/me");
    if (!data) throw new Error("Could not load operator profile");
    setUser({ username: data.username, role: data.role as Role });
  }, []);

  const signOut = useCallback(() => {
    clearTokens();
    setAuthToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, signIn, signOut }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

/** Protected-route wrapper — redirects to /login when there is no session. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null; // brief — session restore in flight
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

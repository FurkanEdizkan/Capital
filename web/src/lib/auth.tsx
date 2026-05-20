/**
 * Authentication context + protected-route wrapper.
 *
 * Phase 0 scope: this is a CLIENT-SIDE MOCK. There is no engine/API yet, so
 * "signing in" just records a session in localStorage. The shape (user, role,
 * token) matches what the real JWT-backed auth will return, so wiring the
 * engine in a later phase is a drop-in replacement of `signIn`/`signOut`.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";

export type Role = "admin" | "user";

export type User = {
  username: string;
  role: Role;
};

type AuthState = {
  user: User | null;
  signIn: (username: string) => void;
  signOut: () => void;
};

const STORAGE_KEY = "capital.auth";

const AuthContext = createContext<AuthState | null>(null);

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as User;
    if (parsed && typeof parsed.username === "string") return parsed;
  } catch {
    /* ignore corrupt storage */
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(loadUser);

  const signIn = useCallback((username: string) => {
    // Mock: the seeded operator is an admin. Real auth resolves role from the API.
    const next: User = { username: username || "ada", role: "admin" };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setUser(next);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(() => ({ user, signIn, signOut }), [user, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

/** Protected-route wrapper — redirects to /login when there is no session. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

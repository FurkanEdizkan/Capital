import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./lib/auth";
import { Shell } from "./components/shell/Shell";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Markets } from "./pages/Markets";
import { Backtest, History, Settings, Strategies, Users } from "./pages/screens";

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="markets" element={<Markets />} />
          <Route path="strategies" element={<Strategies />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="history" element={<History />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<Users />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

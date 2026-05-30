import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./lib/auth";
import { Shell } from "./components/shell/Shell";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Backtest } from "./pages/Backtest";
import { Connections } from "./pages/Connections";
import { Guide } from "./pages/Guide";
import { History } from "./pages/History";
import { Markets } from "./pages/Markets";
import { News } from "./pages/News";
import { Settings } from "./pages/Settings";
import { Strategies } from "./pages/Strategies";
import { Users } from "./pages/screens";

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
          <Route path="news" element={<News />} />
          <Route path="connections" element={<Connections />} />
          <Route path="history" element={<History />} />
          <Route path="guide" element={<Guide />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<Users />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

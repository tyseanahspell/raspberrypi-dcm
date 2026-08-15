import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { LiveProvider } from "./context/LiveContext";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Remotes } from "./pages/Remotes";
import { RemoteDetail } from "./pages/RemoteDetail";
import { Containers } from "./pages/Containers";
import { Updates } from "./pages/Updates";
import { Tasks } from "./pages/Tasks";
import { Settings } from "./pages/Settings";

function Protected({ children }: { children: ReactNode }) {
  const { username, ready } = useAuth();
  if (!ready) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!username) return <Navigate to="/login" replace />;
  return <LiveProvider>{children}</LiveProvider>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="remotes" element={<Remotes />} />
        <Route path="remotes/:id" element={<RemoteDetail />} />
        <Route path="containers" element={<Containers />} />
        <Route path="updates" element={<Updates />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Login() {
  const { username, login } = useAuth();
  const [user, setUser] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (username) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(user, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={onSubmit} className="panel w-full max-w-md p-8">
        <p className="text-[11px] uppercase tracking-[0.25em] text-berry-400">Raspberry Pi OS</p>
        <h1 className="mt-2 text-2xl font-semibold">Datacenter Manager</h1>
        <p className="mt-2 text-sm text-slate-400">
          Central control plane for fleet health, Docker lifecycle, and software updates.
        </p>
        <label className="mt-6 block text-xs text-slate-400">
          Username
          <input
            value={user}
            onChange={(event) => setUser(event.target.value)}
            className="mt-1 w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
          />
        </label>
        <label className="mt-4 block text-xs text-slate-400">
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm text-white"
          />
        </label>
        {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
        <button
          disabled={busy}
          className="mt-6 w-full rounded-lg bg-berry-600 py-2.5 text-sm font-medium text-white hover:bg-berry-500 disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

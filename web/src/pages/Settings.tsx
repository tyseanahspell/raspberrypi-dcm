import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Remote } from "../types";

export function Settings() {
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Remote | null>(null);
  const [password, setPassword] = useState({ current_password: "", new_password: "" });
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ enrollment_token: string }>("/api/v1/settings/enrollment-token")
      .then((result) => setToken(result.enrollment_token))
      .catch(() => undefined);
  }, []);

  async function rotate() {
    const result = await api<{ enrollment_token: string }>("/api/v1/settings/enrollment-token/rotate", {
      method: "POST",
    });
    setToken(result.enrollment_token);
    setMessage("Enrollment token rotated. Update agents that still use the old token.");
  }

  async function addRemote(event: FormEvent) {
    event.preventDefault();
    const remote = await api<Remote>("/api/v1/remotes", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    setCreated(remote);
    setName("");
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    await api("/api/v1/auth/password", {
      method: "POST",
      body: JSON.stringify(password),
    });
    setPassword({ current_password: "", new_password: "" });
    setMessage("Password updated.");
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-sm text-slate-400">Enrollment, dedicated agent tokens, and administrator access.</p>
      </div>
      {message && <div className="panel border-emerald-400/20 p-3 text-sm text-emerald-300">{message}</div>}
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="panel p-5">
          <h3 className="text-sm font-medium">Fleet enrollment token</h3>
          <p className="mt-1 text-sm text-slate-400">
            Share this with <code className="text-slate-200">deploy.sh agent</code> so a Pi can join automatically.
          </p>
          <pre className="mt-4 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs">{token || "—"}</pre>
          <button onClick={rotate} className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5">
            Rotate token
          </button>
        </div>
        <form onSubmit={addRemote} className="panel p-5">
          <h3 className="text-sm font-medium">Add a dedicated remote</h3>
          <p className="mt-1 text-sm text-slate-400">
            Creates a node-specific agent token if you prefer not to use the shared enrollment token.
          </p>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            placeholder="pi-lab-02"
            className="mt-4 w-full rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm"
          />
          <button className="mt-4 rounded-lg bg-berry-600 px-3 py-2 text-sm font-medium hover:bg-berry-500">
            Create remote
          </button>
          {created?.agent_token && (
            <pre className="mt-4 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs">
              AGENT_TOKEN={created.agent_token}
            </pre>
          )}
        </form>
        <form onSubmit={changePassword} className="panel p-5 xl:col-span-2">
          <h3 className="text-sm font-medium">Change password</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input
              type="password"
              required
              placeholder="Current password"
              value={password.current_password}
              onChange={(event) => setPassword({ ...password, current_password: event.target.value })}
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm"
            />
            <input
              type="password"
              required
              minLength={8}
              placeholder="New password"
              value={password.new_password}
              onChange={(event) => setPassword({ ...password, new_password: event.target.value })}
              className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-sm"
            />
          </div>
          <button className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5">
            Update password
          </button>
        </form>
      </div>
    </div>
  );
}

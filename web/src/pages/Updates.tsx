import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { StatusPill } from "../components/StatusDot";
import type { PackageUpdate, Task } from "../types";

export function Updates() {
  const { revision } = useLive();
  const [items, setItems] = useState<PackageUpdate[]>([]);
  const [securityOnly, setSecurityOnly] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<PackageUpdate[]>("/api/v1/updates").then(setItems).catch(() => undefined);
  }, [revision]);

  const visible = useMemo(
    () => (securityOnly ? items.filter((item) => item.is_security) : items),
    [items, securityOnly],
  );

  async function refresh() {
    setBusy(true);
    try {
      await api<Task[]>("/api/v1/updates/refresh", { method: "POST" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Software updates</h2>
          <p className="text-sm text-slate-400">
            Available apt packages across the fleet, including Debian security patches.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            <input
              type="checkbox"
              checked={securityOnly}
              onChange={(event) => setSecurityOnly(event.target.checked)}
            />
            Security only
          </label>
          <button
            onClick={refresh}
            disabled={busy}
            className="rounded-lg bg-berry-600 px-3 py-2 text-sm font-medium hover:bg-berry-500 disabled:opacity-60"
          >
            {busy ? "Queuing…" : "Refresh all remotes"}
          </button>
        </div>
      </div>
      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Package</th>
              <th>Remote</th>
              <th>Current</th>
              <th>Available</th>
              <th>Class</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.id} className="table-row">
                <td className="px-4 py-3 font-medium">{item.package}</td>
                <td>
                  <Link to={`/remotes/${item.remote_id}`} className="hover:text-berry-400">
                    {item.remote_name}
                  </Link>
                </td>
                <td className="font-mono text-xs text-slate-400">{item.current_version || "—"}</td>
                <td className="font-mono text-xs text-slate-200">{item.new_version}</td>
                <td>
                  <StatusPill status={item.is_security ? "security" : "available"} />
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  No pending updates reported. Refresh remotes to scan apt.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

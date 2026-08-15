import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { percent, timeAgo, uptime } from "../lib/format";
import { MetricBar, StatusPill } from "../components/StatusDot";
import type { Remote } from "../types";

export function Remotes() {
  const { revision } = useLive();
  const [remotes, setRemotes] = useState<Remote[]>([]);

  useEffect(() => {
    api<Remote[]>("/api/v1/remotes").then(setRemotes).catch(() => undefined);
  }, [revision]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold">Remotes</h2>
        <p className="text-sm text-slate-400">Registered Raspberry Pi nodes and their current load.</p>
      </div>
      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Node</th>
              <th>Status</th>
              <th>Resources</th>
              <th>Uptime</th>
              <th>Seen</th>
            </tr>
          </thead>
          <tbody>
            {remotes.map((remote) => (
              <tr key={remote.id} className="table-row">
                <td className="px-4 py-3">
                  <Link to={`/remotes/${remote.id}`} className="font-medium hover:text-berry-400">
                    {remote.name}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {remote.hostname || "pending enrollment"} · {remote.os_pretty || "Raspberry Pi OS"}
                  </p>
                </td>
                <td>
                  <StatusPill status={remote.status} />
                  {(remote.under_voltage || remote.thermal_throttled) && (
                    <p className="mt-1 text-xs text-amber-300">
                      {remote.under_voltage && "undervoltage "}
                      {remote.thermal_throttled && "throttled"}
                    </p>
                  )}
                </td>
                <td className="space-y-2 py-3 pr-6">
                  <MetricBar label="CPU" value={remote.cpu_percent} />
                  <MetricBar label="MEM" value={percent(remote.mem_used, remote.mem_total)} />
                </td>
                <td className="text-slate-300">{remote.uptime_seconds ? uptime(remote.uptime_seconds) : "—"}</td>
                <td className="text-slate-400">{timeAgo(remote.last_seen)}</td>
              </tr>
            ))}
            {remotes.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  No remotes registered.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

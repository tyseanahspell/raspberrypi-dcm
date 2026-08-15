import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { bytes, percent, timeAgo, uptime } from "../lib/format";
import { MetricBar, StatusPill } from "../components/StatusDot";
import type { Container, MetricPoint, Remote, Task } from "../types";

export function RemoteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { revision } = useLive();
  const [remote, setRemote] = useState<Remote | null>(null);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [containers, setContainers] = useState<Container[]>([]);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api<Remote>(`/api/v1/remotes/${id}`),
      api<MetricPoint[]>(`/api/v1/remotes/${id}/metrics`),
      api<Container[]>(`/api/v1/containers?remote_id=${id}`),
    ]).then(([nextRemote, nextMetrics, nextContainers]) => {
      setRemote(nextRemote);
      setMetrics(nextMetrics);
      setContainers(nextContainers);
    });
  }, [id, revision]);

  async function act(action: "reboot" | "shutdown" | "start" | "stop" | "restart", containerId?: string) {
    if (!id) return;
    const key = containerId ? `${action}-${containerId}` : action;
    setBusy(key);
    try {
      if (containerId) {
        await api<Task>(`/api/v1/containers/${containerId}/${action}`, { method: "POST" });
      } else {
        if (!window.confirm(`Send ${action} to this Raspberry Pi?`)) return;
        await api<Task>(`/api/v1/remotes/${id}/${action}`, { method: "POST" });
      }
    } finally {
      setBusy("");
    }
  }

  async function removeRemote() {
    if (!id || !window.confirm("Remove this remote from the manager?")) return;
    await api(`/api/v1/remotes/${id}`, { method: "DELETE" });
    navigate("/remotes");
  }

  if (!remote) return <p className="text-sm text-slate-500">Loading remote…</p>;

  const chart = metrics.map((point) => ({
    ...point,
    time: new Date(point.captured_at).toLocaleTimeString(),
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/remotes" className="text-xs text-slate-500 hover:text-slate-300">
            ← Remotes
          </Link>
          <h2 className="mt-1 text-2xl font-semibold">{remote.name}</h2>
          <p className="text-sm text-slate-400">
            {remote.model || "Raspberry Pi"} · {remote.os_pretty || "awaiting inventory"} · {remote.arch}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => act("reboot")}
            disabled={!!busy}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm hover:bg-white/5"
          >
            Reboot
          </button>
          <button
            onClick={() => act("shutdown")}
            disabled={!!busy}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm hover:bg-white/5"
          >
            Shutdown
          </button>
          <button
            onClick={removeRemote}
            className="rounded-lg border border-rose-400/30 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-400/10"
          >
            Remove
          </button>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        <div className="panel p-4">
          <p className="text-xs text-slate-500">Status</p>
          <div className="mt-2">
            <StatusPill status={remote.status} />
          </div>
          <p className="mt-3 text-xs text-slate-500">Seen {timeAgo(remote.last_seen)}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs text-slate-500">Uptime</p>
          <p className="mt-2 text-xl font-semibold">{remote.uptime_seconds ? uptime(remote.uptime_seconds) : "—"}</p>
          <p className="mt-1 text-xs text-slate-500">{remote.cpu_count} cores · load {remote.load_1.toFixed(2)}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs text-slate-500">Memory / Disk</p>
          <p className="mt-2 text-sm">
            {bytes(remote.mem_used)} / {bytes(remote.mem_total)}
          </p>
          <p className="text-xs text-slate-500">
            {bytes(remote.disk_used)} / {bytes(remote.disk_total)}
          </p>
        </div>
        <div className="panel p-4">
          <p className="text-xs text-slate-500">Thermal</p>
          <p className="mt-2 text-xl font-semibold">
            {remote.temperature_c != null ? `${remote.temperature_c}°C` : "n/a"}
          </p>
          <p className="text-xs text-amber-300">
            {remote.under_voltage && "Undervoltage "}
            {remote.thermal_throttled && "Throttled"}
            {!remote.under_voltage && !remote.thermal_throttled && "Stable"}
          </p>
        </div>
      </div>
      <div className="panel p-4">
        <h3 className="mb-3 text-sm font-medium">Resource history</h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart}>
              <XAxis dataKey="time" hide />
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                contentStyle={{ background: "#181c25", border: "1px solid rgba(255,255,255,0.1)" }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Area type="monotone" dataKey="cpu_percent" stroke="#e30b5d" fill="#e30b5d33" name="CPU %" />
              <Area type="monotone" dataKey="mem_percent" stroke="#38bdf8" fill="#38bdf833" name="Memory %" />
              <Area type="monotone" dataKey="temperature_c" stroke="#f5a524" fill="#f5a52422" name="Temp °C" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="panel overflow-hidden">
        <div className="border-b border-white/10 px-4 py-3 text-sm font-medium">Docker containers</div>
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th>Image</th>
              <th>State</th>
              <th>CPU / Mem</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {containers.map((container) => (
              <tr key={container.id} className="table-row">
                <td className="px-4 py-3 font-medium">{container.name}</td>
                <td className="max-w-xs truncate text-slate-400">{container.image}</td>
                <td>
                  <StatusPill status={container.state} />
                </td>
                <td className="py-3 pr-4">
                  <MetricBar label="CPU" value={container.cpu_percent} />
                  <div className="mt-2">
                    <MetricBar label="MEM" value={percent(container.mem_usage, container.mem_limit)} />
                  </div>
                </td>
                <td className="px-4">
                  <div className="flex gap-2">
                    <button
                      disabled={!!busy}
                      onClick={() => act("start", container.id)}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Start
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => act("stop", container.id)}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Stop
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => act("restart", container.id)}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Restart
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {containers.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No containers reported by this agent.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

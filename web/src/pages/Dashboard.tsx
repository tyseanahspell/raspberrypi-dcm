import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Box, Cpu, Package, Radio, Thermometer } from "lucide-react";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { bytes, percent, timeAgo } from "../lib/format";
import { MetricBar, StatusPill } from "../components/StatusDot";
import type { Dashboard as DashboardData } from "../types";

function Stat({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Radio;
}) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between text-slate-400">
        <p className="text-xs uppercase tracking-wide">{label}</p>
        <Icon className="h-4 w-4" />
      </div>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function Dashboard() {
  const { revision } = useLive();
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    api<DashboardData>("/api/v1/dashboard").then(setData).catch(() => undefined);
  }, [revision]);

  if (!data) {
    return <p className="text-sm text-slate-500">Loading fleet snapshot…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Global dashboard</h2>
        <p className="text-sm text-slate-400">
          Real-time health, load, and resource pressure across every registered Raspberry Pi.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Remotes"
          value={`${data.remotes_online}/${data.remotes_total}`}
          hint={`${data.remotes_degraded} degraded · ${data.remotes_offline} offline`}
          icon={Radio}
        />
        <Stat
          label="Containers"
          value={`${data.containers_running}/${data.containers_total}`}
          hint={`${data.containers_stopped} stopped`}
          icon={Box}
        />
        <Stat
          label="Fleet load"
          value={`${data.avg_cpu_percent.toFixed(1)}% CPU`}
          hint={`${data.avg_mem_percent.toFixed(1)}% memory average`}
          icon={Cpu}
        />
        <Stat
          label="Updates"
          value={data.updates_available}
          hint={`${data.security_updates} security · ${data.failed_tasks_24h} failed tasks / 24h`}
          icon={Package}
        />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="panel xl:col-span-2 overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <h3 className="text-sm font-medium">Infrastructure health</h3>
            <span className="text-xs text-slate-500">
              Hottest SoC {data.hottest_temp_c != null ? `${data.hottest_temp_c}°C` : "n/a"}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Remote</th>
                <th>Status</th>
                <th>CPU / Memory / Disk</th>
                <th>Load</th>
                <th>Temp</th>
                <th>Guests</th>
              </tr>
            </thead>
            <tbody>
              {data.remotes.map((remote) => (
                <tr key={remote.id} className="table-row">
                  <td className="px-4 py-3">
                    <Link to={`/remotes/${remote.id}`} className="font-medium hover:text-berry-400">
                      {remote.name}
                    </Link>
                    <p className="text-xs text-slate-500">{remote.model || remote.hostname || "Awaiting agent"}</p>
                  </td>
                  <td>
                    <StatusPill status={remote.status} />
                  </td>
                  <td className="space-y-2 py-3 pr-4">
                    <MetricBar label="CPU" value={remote.cpu_percent} />
                    <MetricBar label="MEM" value={percent(remote.mem_used, remote.mem_total)} />
                    <MetricBar label="DSK" value={percent(remote.disk_used, remote.disk_total)} />
                  </td>
                  <td className="font-mono text-xs text-slate-300">
                    {remote.load_1.toFixed(2)} / {remote.load_5.toFixed(2)} / {remote.load_15.toFixed(2)}
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-xs">
                      <Thermometer className="h-3.5 w-3.5 text-slate-500" />
                      {remote.temperature_c != null ? `${remote.temperature_c}°C` : "—"}
                    </span>
                  </td>
                  <td className="text-xs text-slate-300">
                    {remote.container_running}/{remote.container_total}
                    {remote.updates_available > 0 && (
                      <p className="text-amber-300">{remote.updates_available} updates</p>
                    )}
                  </td>
                </tr>
              ))}
              {data.remotes.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                    No remotes yet. Deploy an agent or add a node in Settings.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="space-y-4">
          <div className="panel p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <Activity className="h-4 w-4 text-berry-400" />
              Attention
            </div>
            <div className="space-y-3">
              {data.outliers.length === 0 && <p className="text-sm text-slate-500">No outliers detected.</p>}
              {data.outliers.map((remote) => (
                <Link key={remote.id} to={`/remotes/${remote.id}`} className="block rounded-lg bg-white/5 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{remote.name}</p>
                    <StatusPill status={remote.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    CPU {remote.cpu_percent.toFixed(0)}% · MEM {percent(remote.mem_used, remote.mem_total)}% ·{" "}
                    {remote.updates_available} updates
                  </p>
                </Link>
              ))}
            </div>
          </div>
          <div className="panel p-4">
            <div className="mb-3 text-sm font-medium">Recent tasks</div>
            <div className="space-y-2">
              {data.recent_tasks.map((task) => (
                <div key={task.id} className="flex items-start justify-between gap-3 text-sm">
                  <div>
                    <p className="font-medium">
                      {task.type} {task.target}
                    </p>
                    <p className="text-xs text-slate-500">
                      {task.remote_name || "manager"} · {timeAgo(task.created_at)}
                    </p>
                  </div>
                  <StatusPill status={task.status} />
                </div>
              ))}
              {data.recent_tasks.length === 0 && <p className="text-sm text-slate-500">No tasks yet.</p>}
            </div>
          </div>
        </div>
      </div>
      <div className="panel overflow-hidden">
        <div className="border-b border-white/10 px-4 py-3 text-sm font-medium">Capacity snapshot</div>
        <div className="grid gap-4 p-4 md:grid-cols-3">
          {data.remotes.map((remote) => (
            <div key={remote.id} className="rounded-lg bg-white/5 p-3">
              <p className="text-sm font-medium">{remote.name}</p>
              <p className="text-xs text-slate-500">
                {bytes(remote.mem_used)} / {bytes(remote.mem_total)} · {bytes(remote.disk_used)} disk
              </p>
              <div className="mt-3 space-y-2">
                <MetricBar label="CPU" value={remote.cpu_percent} />
                <MetricBar label="Memory" value={percent(remote.mem_used, remote.mem_total)} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

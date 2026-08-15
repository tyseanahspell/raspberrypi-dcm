import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { percent } from "../lib/format";
import { MetricBar, StatusPill } from "../components/StatusDot";
import type { Container, Task } from "../types";

export function Containers() {
  const { revision } = useLive();
  const [items, setItems] = useState<Container[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api<Container[]>("/api/v1/containers").then(setItems).catch(() => undefined);
  }, [revision]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) =>
      [item.name, item.image, item.remote_name, item.compose_project].join(" ").toLowerCase().includes(needle),
    );
  }, [items, filter]);

  async function act(id: string, action: "start" | "stop" | "restart") {
    setBusy(`${id}-${action}`);
    try {
      await api<Task>(`/api/v1/containers/${id}/${action}`, { method: "POST" });
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Containers</h2>
          <p className="text-sm text-slate-400">Start, stop, and restart Docker guests from the control plane.</p>
        </div>
        <input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter by name, image, or remote"
          className="w-72 rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm"
        />
      </div>
      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Container</th>
              <th>Remote</th>
              <th>State</th>
              <th>Resources</th>
              <th>Ports</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.id} className="table-row">
                <td className="px-4 py-3">
                  <p className="font-medium">{item.name}</p>
                  <p className="max-w-md truncate text-xs text-slate-500">{item.image}</p>
                </td>
                <td>
                  <Link to={`/remotes/${item.remote_id}`} className="text-slate-300 hover:text-berry-400">
                    {item.remote_name}
                  </Link>
                </td>
                <td>
                  <StatusPill status={item.state} />
                  {item.health && <p className="mt-1 text-xs text-slate-500">{item.health}</p>}
                </td>
                <td className="py-3 pr-4">
                  <MetricBar label="CPU" value={item.cpu_percent} />
                  <div className="mt-2">
                    <MetricBar label="MEM" value={percent(item.mem_usage, item.mem_limit)} />
                  </div>
                </td>
                <td className="text-xs text-slate-400">
                  {item.ports.slice(0, 3).map((port, index) => (
                    <div key={`${item.id}-${index}`}>{port.host || port.container}</div>
                  ))}
                </td>
                <td className="px-4">
                  <div className="flex gap-2">
                    <button
                      disabled={!!busy}
                      onClick={() => act(item.id, "start")}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Start
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => act(item.id, "stop")}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Stop
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => act(item.id, "restart")}
                      className="rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/5"
                    >
                      Restart
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                  No containers match the current view.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

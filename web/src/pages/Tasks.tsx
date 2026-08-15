import { useEffect, useState } from "react";
import { useLive } from "../context/LiveContext";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import { StatusPill } from "../components/StatusDot";
import type { Task } from "../types";

export function Tasks() {
  const { revision } = useLive();
  const [items, setItems] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);

  useEffect(() => {
    api<Task[]>("/api/v1/tasks").then(setItems).catch(() => undefined);
  }, [revision]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold">Task log</h2>
        <p className="text-sm text-slate-400">Aggregated lifecycle and maintenance jobs from every remote.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="panel overflow-hidden xl:col-span-2">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Task</th>
                <th>Remote</th>
                <th>Status</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="table-row cursor-pointer"
                  onClick={() => setSelected(item)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium">
                      {item.type} {item.target}
                    </p>
                    <p className="text-xs text-slate-500">by {item.requested_by}</p>
                  </td>
                  <td className="text-slate-300">{item.remote_name || "—"}</td>
                  <td>
                    <StatusPill status={item.status} />
                  </td>
                  <td className="text-slate-400">{timeAgo(item.created_at)}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-slate-500">
                    No tasks have been recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="panel p-4">
          <h3 className="text-sm font-medium">Details</h3>
          {!selected && <p className="mt-3 text-sm text-slate-500">Select a task to inspect its log.</p>}
          {selected && (
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <p className="font-medium">
                  {selected.type} {selected.target}
                </p>
                <StatusPill status={selected.status} />
              </div>
              <p className="text-slate-400">
                {selected.remote_name || "manager"} · {selected.requested_by}
              </p>
              {selected.error && <p className="text-rose-300">{selected.error}</p>}
              <pre className="max-h-80 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs text-slate-300">
                {selected.log || "No output yet."}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

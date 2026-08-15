import { statusTone } from "../lib/format";

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusTone(status)}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function MetricBar({
  label,
  value,
  warn = 80,
  danger = 90,
}: {
  label: string;
  value: number;
  warn?: number;
  danger?: number;
}) {
  const tone = value >= danger ? "bg-rose-400" : value >= warn ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="min-w-[8rem]">
      <div className="mb-1 flex justify-between text-[11px] text-slate-400">
        <span>{label}</span>
        <span className="font-mono text-slate-200">{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full ${tone}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}

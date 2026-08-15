export function bytes(value: number): string {
  if (!value) return "0 B";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function percent(used: number, total: number): number {
  if (!total) return 0;
  return Math.round((used / total) * 1000) / 10;
}

export function uptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function timeAgo(value: string | null): string {
  if (!value) return "never";
  const delta = Date.now() - new Date(value).getTime();
  const seconds = Math.max(0, Math.floor(delta / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function statusTone(status: string): string {
  switch (status) {
    case "online":
    case "running":
    case "ok":
    case "healthy":
      return "text-emerald-400 bg-emerald-400/10";
    case "degraded":
    case "paused":
    case "queued":
    case "running_task":
      return "text-amber-300 bg-amber-400/10";
    case "offline":
    case "error":
    case "exited":
    case "dead":
    case "security":
      return "text-rose-300 bg-rose-400/10";
    case "pending":
    case "created":
      return "text-sky-300 bg-sky-400/10";
    default:
      return "text-slate-300 bg-white/10";
  }
}

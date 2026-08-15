export type Remote = {
  id: string;
  name: string;
  hostname: string;
  status: string;
  last_seen: string | null;
  os_pretty: string;
  kernel: string;
  arch: string;
  model: string;
  tags: string;
  notes: string;
  cpu_percent: number;
  mem_used: number;
  mem_total: number;
  disk_used: number;
  disk_total: number;
  load_1: number;
  load_5: number;
  load_15: number;
  temperature_c: number | null;
  uptime_seconds: number;
  cpu_count: number;
  under_voltage: boolean;
  thermal_throttled: boolean;
  docker_available: boolean;
  container_running: number;
  container_total: number;
  updates_available: number;
  security_updates: number;
  agent_token?: string;
};

export type Container = {
  id: string;
  remote_id: string;
  remote_name: string;
  docker_id: string;
  name: string;
  image: string;
  status: string;
  state: string;
  health: string;
  cpu_percent: number;
  mem_usage: number;
  mem_limit: number;
  ports: { container: string; host: string | null }[];
  created: string;
  compose_project: string;
};

export type Task = {
  id: string;
  remote_id: string | null;
  remote_name: string;
  type: string;
  target: string;
  status: string;
  requested_by: string;
  log: string;
  error: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type PackageUpdate = {
  id: string;
  remote_id: string;
  remote_name: string;
  package: string;
  current_version: string;
  new_version: string;
  is_security: boolean;
  origin: string;
};

export type MetricPoint = {
  captured_at: string;
  cpu_percent: number;
  mem_percent: number;
  disk_percent: number;
  load_1: number;
  temperature_c: number | null;
};

export type SearchHit = {
  kind: string;
  id: string;
  title: string;
  subtitle: string;
  href: string;
  status: string;
};

export type Dashboard = {
  remotes_total: number;
  remotes_online: number;
  remotes_offline: number;
  remotes_degraded: number;
  containers_running: number;
  containers_stopped: number;
  containers_total: number;
  updates_available: number;
  security_updates: number;
  failed_tasks_24h: number;
  running_tasks: number;
  hottest_temp_c: number | null;
  avg_cpu_percent: number;
  avg_mem_percent: number;
  remotes: Remote[];
  recent_tasks: Task[];
  outliers: Remote[];
};

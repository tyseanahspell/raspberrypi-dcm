from __future__ import annotations

import json
import logging
import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import docker
import httpx
import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("rpdm-agent")

MANAGER_URL = os.environ.get("MANAGER_URL", "http://manager:8080").rstrip("/")
ENROLLMENT_TOKEN = os.environ.get("ENROLLMENT_TOKEN", "")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
AGENT_NAME = os.environ.get("AGENT_NAME", "")
STATE_FILE = Path(os.environ.get("AGENT_STATE_FILE", "/data/agent.json"))
HEARTBEAT_SECONDS = int(os.environ.get("HEARTBEAT_SECONDS", "5"))
COMMAND_SECONDS = float(os.environ.get("COMMAND_SECONDS", "2"))
UPDATE_SECONDS = int(os.environ.get("UPDATE_SECONDS", "900"))
HOST_ROOT = Path(os.environ.get("HOST_ROOT", "/host"))
HOST_PROC = Path(os.environ.get("HOST_PROC", "/host/proc"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def host_path(path: str) -> Path:
    if HOST_ROOT.exists():
        return HOST_ROOT / path.lstrip("/")
    return Path(path)


def nsenter(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    command = ["nsenter", "-t", "1", "-m", "-u", "-i", "-n", "--", *args]
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def load_state() -> dict[str, str]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def collect_identity() -> dict[str, Any]:
    model = _read_text(host_path("/proc/device-tree/model")).replace("\x00", "")
    if not model:
        model = _read_text(Path("/proc/device-tree/model")).replace("\x00", "")
    os_pretty = ""
    os_release = host_path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("PRETTY_NAME="):
                os_pretty = line.split("=", 1)[1].strip().strip('"')
    hostname = _read_text(host_path("/etc/hostname")) or socket.gethostname()
    return {
        "hostname": hostname,
        "os_pretty": os_pretty or platform.platform(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "model": model or platform.processor() or platform.machine(),
    }


def read_temperature() -> float | None:
    candidates = [
        host_path("/sys/class/thermal/thermal_zone0/temp"),
        Path("/sys/class/thermal/thermal_zone0/temp"),
    ]
    for path in candidates:
        raw = _read_text(path)
        if raw.isdigit():
            value = int(raw)
            return round(value / 1000, 1) if value > 200 else float(value)
    return None


def read_throttled() -> dict[str, Any]:
    result = {"throttled": "", "under_voltage": False, "thermal_throttled": False}
    try:
        proc = nsenter(["vcgencmd", "get_throttled"], timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return result
    if proc.returncode != 0:
        return result
    text = (proc.stdout or "").strip()
    if "throttled=" not in text:
        return result
    hex_value = text.split("=", 1)[1].strip()
    try:
        bits = int(hex_value, 16)
    except ValueError:
        return result
    result["throttled"] = hex_value
    result["under_voltage"] = bool(bits & 0x1 or bits & (1 << 16))
    result["thermal_throttled"] = bool(bits & 0x4 or bits & (1 << 18))
    return result


_prev_cpu: tuple[int, int] | None = None


def _host_cpu() -> tuple[float, int]:
    global _prev_cpu
    stat = host_path("/proc/stat")
    if not stat.exists():
        return psutil.cpu_percent(interval=0.4), psutil.cpu_count() or 0
    first = stat.read_text(encoding="utf-8", errors="replace").splitlines()[0].split()
    values = [int(item) for item in first[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    cpu_count = sum(1 for line in stat.read_text(encoding="utf-8").splitlines() if line.startswith("cpu"))
    cpu_count = max(cpu_count - 1, 1)
    if _prev_cpu is None:
        _prev_cpu = (idle, total)
        time.sleep(0.4)
        return _host_cpu()
    prev_idle, prev_total = _prev_cpu
    _prev_cpu = (idle, total)
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return 0.0, cpu_count
    return round((1 - idle_delta / total_delta) * 100, 1), cpu_count


def _host_memory() -> tuple[int, int]:
    meminfo = host_path("/proc/meminfo")
    if not meminfo.exists():
        vm = psutil.virtual_memory()
        return int(vm.used), int(vm.total)
    data: dict[str, int] = {}
    for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            data[parts[0].rstrip(":")] = int(parts[1]) * 1024
    total = data.get("MemTotal", 0)
    available = data.get("MemAvailable", data.get("MemFree", 0))
    return max(total - available, 0), total


def _host_load() -> tuple[float, float, float]:
    loadavg = host_path("/proc/loadavg")
    if loadavg.exists():
        parts = loadavg.read_text(encoding="utf-8").split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    return os.getloadavg()


def _host_uptime() -> int:
    uptime = host_path("/proc/uptime")
    if uptime.exists():
        return int(float(uptime.read_text(encoding="utf-8").split()[0]))
    return int(time.time() - psutil.boot_time())


def collect_metrics() -> dict[str, Any]:
    disk_target = HOST_ROOT if HOST_ROOT.exists() else Path("/")
    try:
        disk = psutil.disk_usage(str(disk_target))
    except OSError:
        disk = psutil.disk_usage("/")
    load1, load5, load15 = _host_load()
    mem_used, mem_total = _host_memory()
    cpu_percent, cpu_count = _host_cpu()
    net = psutil.net_io_counters()
    throttle = read_throttled()
    docker_ok = False
    try:
        client = docker.from_env()
        client.ping()
        docker_ok = True
    except Exception:
        docker_ok = False
    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "mem_used": mem_used,
        "mem_total": mem_total,
        "disk_used": int(disk.used),
        "disk_total": int(disk.total),
        "load_1": float(load1),
        "load_5": float(load5),
        "load_15": float(load15),
        "temperature_c": read_temperature(),
        "uptime_seconds": _host_uptime(),
        "net_rx_bytes": int(getattr(net, "bytes_recv", 0)),
        "net_tx_bytes": int(getattr(net, "bytes_sent", 0)),
        "docker_available": docker_ok,
        **throttle,
    }


def _container_stats(container: Any) -> tuple[float, int, int]:
    try:
        stats = container.stats(stream=False)
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"][
            "total_usage"
        ]
        system_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - stats["precpu_stats"].get(
            "system_cpu_usage", 0
        )
        online = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"]["cpu_usage"].get("percpu_usage") or [1]
        )
        cpu = (cpu_delta / system_delta) * online * 100 if system_delta else 0.0
        mem = int(stats.get("memory_stats", {}).get("usage") or 0)
        limit = int(stats.get("memory_stats", {}).get("limit") or 0)
        return round(cpu, 1), mem, limit
    except Exception:
        return 0.0, 0, 0


def collect_containers() -> list[dict[str, Any]]:
    try:
        client = docker.from_env()
        items = []
        for container in client.containers.list(all=True):
            labels = container.labels or {}
            ports = []
            for key, bindings in (container.attrs.get("NetworkSettings", {}).get("Ports") or {}).items():
                if not bindings:
                    ports.append({"container": key, "host": None})
                    continue
                for binding in bindings:
                    ports.append(
                        {
                            "container": key,
                            "host": f"{binding.get('HostIp', '')}:{binding.get('HostPort', '')}",
                        }
                    )
            cpu, mem, limit = (0.0, 0, 0)
            if container.status == "running":
                cpu, mem, limit = _container_stats(container)
            health = ""
            state = container.attrs.get("State") or {}
            if isinstance(state.get("Health"), dict):
                health = str(state["Health"].get("Status") or "")
            items.append(
                {
                    "docker_id": container.id,
                    "name": container.name,
                    "image": container.image.tags[0]
                    if container.image.tags
                    else container.attrs.get("Config", {}).get("Image", ""),
                    "status": container.status,
                    "state": "running" if container.status == "running" else container.status,
                    "health": health,
                    "cpu_percent": cpu,
                    "mem_usage": mem,
                    "mem_limit": limit,
                    "ports": ports,
                    "created": container.attrs.get("Created", ""),
                    "compose_project": labels.get("com.docker.compose.project", ""),
                }
            )
        return items
    except Exception as exc:
        logger.warning("Docker inventory unavailable: %s", exc)
        return []


def collect_updates() -> list[dict[str, Any]]:
    try:
        nsenter(["apt-get", "update", "-qq"], timeout=90)
        proc = nsenter(["apt-get", "-s", "dist-upgrade"], timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Update scan failed: %s", exc)
        return []
    if proc.returncode != 0:
        logger.warning("apt simulation failed: %s", proc.stderr.strip())
        return []
    packages: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        if not line.startswith("Inst "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[1]
        new_version = parts[2].strip("[]")
        current = ""
        if "(" in line and ")" in line:
            current = line[line.find("(") + 1 : line.find(")")].split()[0]
        security = "Debian-Security" in line or "-security" in line.lower()
        packages.append(
            {
                "package": name,
                "current_version": current,
                "new_version": new_version,
                "is_security": security,
                "origin": "apt",
            }
        )
    return packages


class ManagerClient:
    def __init__(self) -> None:
        self.token = AGENT_TOKEN or load_state().get("agent_token", "")
        self.client = httpx.Client(timeout=20.0)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def enroll(self) -> None:
        if self.token:
            return
        if not ENROLLMENT_TOKEN:
            raise RuntimeError("ENROLLMENT_TOKEN or AGENT_TOKEN is required")
        identity = collect_identity()
        response = self.client.post(
            f"{MANAGER_URL}/api/v1/agent/enroll",
            json={
                "enrollment_token": ENROLLMENT_TOKEN,
                "hostname": identity["hostname"],
                "name": AGENT_NAME or identity["hostname"],
            },
        )
        response.raise_for_status()
        body = response.json()
        self.token = body["agent_token"]
        save_state({"agent_token": self.token, "agent_id": body["agent_id"]})
        logger.info("Enrolled as remote %s (%s)", body["name"], body["remote_id"])

    def heartbeat(self, include_updates: bool) -> None:
        payload = {
            "metrics": collect_metrics(),
            "containers": collect_containers(),
            "identity": collect_identity(),
        }
        if include_updates:
            payload["updates"] = collect_updates()
        response = self.client.post(
            f"{MANAGER_URL}/api/v1/agent/heartbeat",
            headers=self._headers(),
            json=payload,
        )
        if response.status_code == 401 and ENROLLMENT_TOKEN:
            self.token = ""
            STATE_FILE.unlink(missing_ok=True)
            self.enroll()
            return
        response.raise_for_status()

    def poll_commands(self) -> None:
        response = self.client.get(
            f"{MANAGER_URL}/api/v1/agent/commands",
            headers=self._headers(),
        )
        response.raise_for_status()
        for command in response.json():
            self.execute(command)

    def report(self, task_id: str, status: str, log: str = "", error: str = "") -> None:
        self.client.post(
            f"{MANAGER_URL}/api/v1/agent/task-result",
            headers=self._headers(),
            json={"task_id": task_id, "status": status, "log": log, "error": error},
        ).raise_for_status()

    def execute(self, command: dict[str, Any]) -> None:
        action = command.get("action")
        payload = command.get("payload") or {}
        task_id = command["task_id"]
        logger.info("Executing %s", action)
        try:
            if action in {"container_start", "container_stop", "container_restart"}:
                log = docker_action(action.split("_", 1)[1], payload)
                self.report(task_id, "ok", log=log)
            elif action == "refresh_updates":
                updates = collect_updates()
                self.heartbeat(include_updates=True)
                self.report(task_id, "ok", log=f"Found {len(updates)} available package updates")
            elif action in {"reboot", "shutdown"}:
                verb = "reboot" if action == "reboot" else "poweroff"
                proc = nsenter(["systemctl", verb], timeout=15)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.strip() or f"{verb} failed")
                self.report(task_id, "ok", log=f"Host {verb} requested")
            else:
                self.report(task_id, "error", error=f"Unsupported action {action}")
        except Exception as exc:
            logger.exception("Command %s failed", action)
            try:
                self.report(task_id, "error", error=str(exc))
            except Exception:
                logger.exception("Failed to report task error")


def docker_action(action: str, payload: dict[str, Any]) -> str:
    client = docker.from_env()
    docker_id = payload.get("docker_id")
    if not docker_id:
        raise RuntimeError("Missing docker_id")
    container = client.containers.get(docker_id)
    if action == "start":
        container.start()
    elif action == "stop":
        container.stop(timeout=20)
    elif action == "restart":
        container.restart(timeout=20)
    else:
        raise RuntimeError(f"Unsupported docker action {action}")
    container.reload()
    return f"{container.name} is {container.status}"


def main() -> None:
    client = ManagerClient()
    last_update = 0.0
    last_command = 0.0
    cycles = 0
    logger.info("Agent starting; manager=%s", MANAGER_URL)
    while True:
        try:
            client.enroll()
            now = time.time()
            include_updates = cycles == 1 or (cycles > 1 and now - last_update >= UPDATE_SECONDS)
            client.heartbeat(include_updates=include_updates)
            if include_updates:
                last_update = now
            if now - last_command >= COMMAND_SECONDS:
                client.poll_commands()
                last_command = now
            cycles += 1
        except Exception as exc:
            logger.warning("Agent loop error: %s", exc)
        time.sleep(HEARTBEAT_SECONDS)


if __name__ == "__main__":
    main()

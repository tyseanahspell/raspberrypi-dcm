# Raspberry Pi Datacenter Manager

A production control plane for Raspberry Pi OS fleets. It provides the same operational shape as Proxmox Datacenter Manager: a global dashboard, fast search, aggregated task logs, guest lifecycle actions, and software-update visibility — adapted to Raspberry Pi hosts and Docker containers.

The manager is an overlay. If it is down, every Pi and container keeps running.

## Capabilities

- **Global dashboard** — live health, CPU/memory/disk pressure, load averages, SoC temperature, undervoltage/throttle flags, and outlier highlighting
- **Fast global search** — `Ctrl+K` across remotes, containers, apt packages, and tasks
- **Docker lifecycle** — start, stop, and restart containers from the central UI
- **Update monitoring** — fleet-wide apt upgrade inventory, with security updates called out
- **Task log** — queued, running, and completed jobs with per-task output
- **Multi-node remotes** — enroll additional Pis with a shared token or a dedicated agent token

## Architecture

```
Browser  ──REST + WebSocket──►  Web (nginx)  ──►  Manager API
                                                     ▲
                                        heartbeat / commands
                                                     │
                                        Agent on each Raspberry Pi
                                        (metrics, Docker, apt)
```

- **Manager** — FastAPI + SQLite (WAL), JWT auth, command queue
- **Web** — React SPA behind nginx
- **Agent** — privileged host-aware collector that talks to the Docker socket and the host apt/systemd namespaces

## Deploy on a Raspberry Pi

On the Pi that should run the control plane:

```bash
sudo ./deploy.sh
```

The script installs Docker Compose if needed, generates secrets in `.env`, builds the images, and starts the stack. When it finishes it prints the URL, admin password, and enrollment token.

Open `http://<pi-ip>:8088` and sign in.

All-in-one mode also starts a local agent so the manager Pi appears on the dashboard.

### Manager only

```bash
sudo ./deploy.sh --manager-only
```

### Join another Raspberry Pi

```bash
sudo ./deploy.sh agent \
  --manager-url http://MANAGER_IP:8088 \
  --token ENROLLMENT_TOKEN
```

Or use a dedicated token created under **Settings → Add a dedicated remote**:

```bash
sudo ./deploy.sh agent \
  --manager-url http://MANAGER_IP:8088 \
  --agent-token AGENT_TOKEN \
  --name pi-lab-02
```

### Useful flags

| Flag | Purpose |
| --- | --- |
| `--port 8088` | Host port for the web UI |
| `--force` | Allow deploy on a non-Pi host (lab/x86) |
| `--skip-docker-install` | Do not install Docker automatically |

## Daily operations

- **Dashboard** — fleet health, load, hottest SoC, failed tasks
- **Containers** — start/stop/restart any Docker guest the agents can see
- **Updates** — review pending packages; **Refresh all remotes** queues a new apt scan
- **Tasks** — inspect command output and failures
- **Settings** — rotate the enrollment token, create remotes, change the admin password

Node reboot/shutdown is available on each remote detail page and is executed on the host via the agent.

## Configuration

`.env` is created from `.env.example` by `deploy.sh`. Important values:

| Variable | Meaning |
| --- | --- |
| `SECRET_KEY` | JWT signing key |
| `ADMIN_USER` / `ADMIN_PASSWORD` | First-boot administrator |
| `ENROLLMENT_TOKEN` | Shared join token for agents |
| `RPDM_PORT` | Published web port |
| `UPDATE_SECONDS` | How often agents rescan apt (default 15 minutes) |

Data lives in the `rpdm-data` Docker volume (`/data/rpdm.db` inside the manager).

## Local development

```bash
# API
cd manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=dev ADMIN_PASSWORD=changeme ENROLLMENT_TOKEN=devjoin DATABASE_URL=sqlite:///./rpdm.db APP_ENV=development
uvicorn app.main:app --reload --port 8080

# UI
cd web
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8080`.

## Security notes

- Change the generated admin password after first login
- Treat `.env` and agent tokens as secrets
- Publish the UI only on a trusted network, or put TLS in front of port `8088`
- Agents need the Docker socket and host namespaces to collect metrics and manage containers

## License

Use and modify freely for your own Raspberry Pi infrastructure.

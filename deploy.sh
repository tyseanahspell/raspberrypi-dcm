#!/usr/bin/env bash
# Deploy Raspberry Pi Datacenter Manager with Docker Compose.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="full"
MANAGER_URL=""
ENROLL_TOKEN=""
AGENT_TOKEN=""
AGENT_NAME="$(hostname)"
RPDM_PORT="${RPDM_PORT:-8088}"
FORCE=0
SKIP_DOCKER_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  ./deploy.sh [--port 8088] [--force] [--skip-docker-install]
  ./deploy.sh --manager-only [--port 8088]
  ./deploy.sh agent --manager-url http://MANAGER:8088 --token ENROLLMENT_TOKEN
  ./deploy.sh agent --manager-url http://MANAGER:8088 --agent-token AGENT_TOKEN

Deploys the web control plane (and a local agent) on Raspberry Pi OS using Docker Compose.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    agent) MODE="agent"; shift ;;
    --manager-only) MODE="manager"; shift ;;
    --manager-url) MANAGER_URL="${2:-}"; shift 2 ;;
    --token) ENROLL_TOKEN="${2:-}"; shift 2 ;;
    --agent-token) AGENT_TOKEN="${2:-}"; shift 2 ;;
    --name) AGENT_NAME="${2:-}"; shift 2 ;;
    --port) RPDM_PORT="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --skip-docker-install) SKIP_DOCKER_INSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

detect_pi() {
  local model=""
  if [[ -r /proc/device-tree/model ]]; then
    model="$(tr -d '\0' </proc/device-tree/model)"
  fi
  if [[ "$model" == *"Raspberry Pi"* ]]; then
    printf '%s\n' "$model"
    return 0
  fi
  return 1
}

ensure_linux() {
  [[ "$(uname -s)" == "Linux" ]] || die "This deploy script targets Raspberry Pi OS (Linux)."
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return 0
  fi
  [[ "$SKIP_DOCKER_INSTALL" -eq 0 ]] || die "Docker Compose is not installed."
  [[ "$(id -u)" -eq 0 ]] || die "Docker is missing. Re-run as root so it can be installed, or install Docker Compose first."
  log "Installing Docker Engine and Compose plugin"
  curl -fsSL https://get.docker.com | sh
  if [[ -n "${SUDO_USER:-}" ]]; then
    usermod -aG docker "$SUDO_USER" || true
  fi
  command -v docker >/dev/null 2>&1 || die "Docker installation failed."
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is missing after install."
}

compose() {
  docker compose "$@"
}

write_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -q "^${key}=" "$file"; then
    local escaped
    escaped="$(printf '%s' "$value" | sed -e 's/[\/&]/\\&/g')"
    sed -i "s/^${key}=.*/${key}=${escaped}/" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

init_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    write_env_value SECRET_KEY "$(random_secret)" .env
    write_env_value ADMIN_PASSWORD "$(random_secret | cut -c1-20)" .env
    write_env_value ENROLLMENT_TOKEN "$(random_secret | cut -c1-32)" .env
    write_env_value RPDM_PORT "$RPDM_PORT" .env
    write_env_value AGENT_NAME "$AGENT_NAME" .env
    log "Wrote .env with generated secrets"
  else
    write_env_value RPDM_PORT "$RPDM_PORT" .env
    write_env_value AGENT_NAME "$AGENT_NAME" .env
    log "Using existing .env"
  fi
}

print_credentials() {
  local port user password token
  port="$(grep '^RPDM_PORT=' .env | cut -d= -f2-)"
  user="$(grep '^ADMIN_USER=' .env | cut -d= -f2-)"
  password="$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"
  token="$(grep '^ENROLLMENT_TOKEN=' .env | cut -d= -f2-)"
  cat <<EOF

Raspberry Pi Datacenter Manager is up.

  URL:                http://$(hostname -I 2>/dev/null | awk '{print $1}'):${port}
  Username:           ${user}
  Password:           ${password}
  Enrollment token:   ${token}

Join another Pi:
  ./deploy.sh agent --manager-url http://THIS_PI:${port} --token ${token}

EOF
}

wait_http() {
  local url="$1"
  local tries=90
  local i
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  compose logs --tail=80 || true
  die "Timed out waiting for ${url}"
}

ensure_linux
need_cmd curl
need_cmd awk

MODEL="$(detect_pi || true)"
if [[ -z "$MODEL" && "$FORCE" -eq 0 ]]; then
  die "This host does not look like a Raspberry Pi. Re-run with --force to deploy anyway."
fi
if [[ -n "$MODEL" ]]; then
  log "Detected ${MODEL}"
else
  log "Non-Pi host allowed by --force"
fi

ensure_docker

if [[ "$MODE" == "agent" ]]; then
  [[ -n "$MANAGER_URL" ]] || die "--manager-url is required for agent mode"
  [[ -n "$ENROLL_TOKEN" || -n "$AGENT_TOKEN" ]] || die "--token or --agent-token is required for agent mode"
  cat >.env.agent <<EOF
MANAGER_URL=${MANAGER_URL}
ENROLLMENT_TOKEN=${ENROLL_TOKEN}
AGENT_TOKEN=${AGENT_TOKEN}
AGENT_NAME=${AGENT_NAME}
EOF
  log "Building and starting the remote agent"
  compose --env-file .env.agent -f docker-compose.agent.yml up -d --build
  log "Agent is reporting to ${MANAGER_URL}"
  exit 0
fi

init_env

if [[ "$MODE" == "manager" ]]; then
  log "Building manager and web UI"
  compose up -d --build manager web
else
  log "Building manager, web UI, and local agent"
  compose up -d --build
fi
wait_http "http://127.0.0.1:${RPDM_PORT}/healthz"
wait_http "http://127.0.0.1:${RPDM_PORT}/api/health"

print_credentials

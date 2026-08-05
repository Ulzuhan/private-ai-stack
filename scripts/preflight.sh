#!/usr/bin/env bash
# Preflight check: verify this machine can run the stack before the first
# `docker compose up -d`. Fails on hard blockers, warns on soft ones.
#
#   ./scripts/preflight.sh
set -euo pipefail

MIN_RAM_GB=8
COMFORTABLE_RAM_GB=16
MIN_DISK_GB=15
COMFORTABLE_DISK_GB=20
MIN_COMPOSE_VERSION="2.30"

failures=0

ok() { printf 'ok    %s\n' "$*"; }
warn() { printf 'warn  %s\n' "$*"; }
fail() {
  printf 'FAIL  %s\n' "$*"
  failures=$((failures + 1))
}

# --- docker and compose ------------------------------------------------------

if ! command -v docker > /dev/null 2>&1; then
  fail "docker is not installed — https://docs.docker.com/get-docker/"
  echo
  echo "${failures} hard blocker(s) found."
  exit 1
fi
ok "docker CLI found"

if ! docker info > /dev/null 2>&1; then
  fail "the docker daemon is not running"
else
  ok "docker daemon is running"
fi

# True if $1 >= $2, dotted numeric compare. `sort -V` would do this in one
# pipe, but BSD sort on macOS does not have it.
version_ge() {
  local IFS=. i h w
  local -a have want
  read -ra have <<< "$1"
  read -ra want <<< "$2"
  for ((i = 0; i < ${#want[@]}; i++)); do
    h=${have[i]:-0}
    w=${want[i]:-0}
    ((10#$h > 10#$w)) && return 0
    ((10#$h < 10#$w)) && return 1
  done
  return 0
}

compose_version=$(docker compose version --short 2> /dev/null | tr -cd '0-9.' || true)
if [ -z "$compose_version" ]; then
  fail "docker compose v2 not found (need ${MIN_COMPOSE_VERSION}+)"
elif version_ge "$compose_version" "$MIN_COMPOSE_VERSION"; then
  ok "docker compose ${compose_version}"
else
  fail "docker compose ${compose_version} is older than ${MIN_COMPOSE_VERSION}"
fi

# --- memory ------------------------------------------------------------------

ram_kb=0
if [ -r /proc/meminfo ]; then
  ram_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
elif command -v sysctl > /dev/null 2>&1; then
  ram_bytes=$(sysctl -n hw.memsize 2> /dev/null || echo 0)
  ram_kb=$((ram_bytes / 1024))
fi
ram_gb=$((ram_kb / 1024 / 1024))

if [ "$ram_gb" -eq 0 ]; then
  warn "could not determine total RAM"
elif [ "$ram_gb" -lt "$MIN_RAM_GB" ]; then
  fail "only ${ram_gb} GB RAM — the stack needs ${MIN_RAM_GB} GB minimum"
elif [ "$ram_gb" -lt "$COMFORTABLE_RAM_GB" ]; then
  warn "${ram_gb} GB RAM — workable, ${COMFORTABLE_RAM_GB} GB is comfortable"
else
  ok "${ram_gb} GB RAM"
fi

# --- disk --------------------------------------------------------------------

# Images plus models need ~15-20 GB; measure the filesystem holding this repo.
disk_kb=$(df -Pk . | awk 'NR==2 {print $4}')
disk_gb=$((disk_kb / 1024 / 1024))
if [ "$disk_gb" -lt "$MIN_DISK_GB" ]; then
  fail "only ${disk_gb} GB free — images and models need ${MIN_DISK_GB} GB minimum"
elif [ "$disk_gb" -lt "$COMFORTABLE_DISK_GB" ]; then
  warn "${disk_gb} GB free — tight; ${COMFORTABLE_DISK_GB} GB recommended"
else
  ok "${disk_gb} GB free disk"
fi

# --- platform hints (informational, never failures) --------------------------

if [ "$(uname -s)" = "Darwin" ]; then
  warn "macOS: containerized Ollama runs CPU-only (no Metal passthrough)."
  warn "       For fast inference use the BYO override with a native Ollama:"
  warn "       docker compose -f docker-compose.yml -f docker-compose.byo.yml up -d"
fi

if command -v nvidia-smi > /dev/null 2>&1; then
  ok "NVIDIA GPU detected"
fi

if curl -fsS --max-time 2 http://localhost:11434/api/version > /dev/null 2>&1; then
  warn "a native Ollama is already listening on localhost:11434 — the BYO"
  warn "       override can reuse it instead of the containerized service"
fi

echo
if [ "$failures" -gt 0 ]; then
  echo "${failures} hard blocker(s) found — fix them before starting the stack."
  exit 1
fi
echo "preflight passed"

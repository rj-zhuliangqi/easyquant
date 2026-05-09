#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

APP_MODULE="${APP_MODULE:-app.main:app}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8010}"
STOP_TIMEOUT="${STOP_TIMEOUT:-15}"
START_TIMEOUT="${START_TIMEOUT:-20}"
PID_FILE="${PID_FILE:-$ROOT_DIR/data/uvicorn.pid}"
LOG_FILE="${LOG_FILE:-$ROOT_DIR/data/uvicorn.log}"

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

log() {
  printf '[service] %s\n' "$*"
}

find_running_pid() {
  local pid=""

  if [[ -f "$PID_FILE" ]]; then
    local candidate
    candidate="$(tr -d '[:space:]' < "$PID_FILE" || true)"
    if [[ "$candidate" =~ ^[0-9]+$ ]] && kill -0 "$candidate" 2>/dev/null; then
      if ps -p "$candidate" -o args= | grep -q "uvicorn $APP_MODULE"; then
        pid="$candidate"
      fi
    fi
  fi

  if [[ -z "$pid" ]] && command -v lsof >/dev/null 2>&1; then
    local listener
    listener="$(lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
    if [[ -n "$listener" ]] && kill -0 "$listener" 2>/dev/null; then
      if ps -p "$listener" -o args= | grep -q "uvicorn $APP_MODULE"; then
        pid="$listener"
      fi
    fi
  fi

  if [[ -z "$pid" ]]; then
    local matched
    matched="$(pgrep -f "uvicorn $APP_MODULE.*--port $PORT" | head -n 1 || true)"
    if [[ -n "$matched" ]] && kill -0 "$matched" 2>/dev/null; then
      pid="$matched"
    fi
  fi

  echo "$pid"
}

stop_pid() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 0
  fi

  log "Found running service pid=$pid, stopping..."
  kill "$pid" 2>/dev/null || true

  local i
  for ((i=1; i<=STOP_TIMEOUT; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      log "Stopped pid=$pid"
      return 0
    fi
    sleep 1
  done

  log "Stop timeout reached, force killing pid=$pid"
  kill -9 "$pid" 2>/dev/null || true
}

build_start_cmd() {
  if [[ -x "$ROOT_DIR/.venv_linux/bin/python" ]]; then
    START_CMD=("$ROOT_DIR/.venv_linux/bin/python" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT")
    return
  fi

  if command -v uv >/dev/null 2>&1; then
    START_CMD=(uv run uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT")
    return
  fi

  START_CMD=(python -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT")
}

wait_until_healthy() {
  local pid="$1"
  local health_host="$HOST"
  local i

  if [[ "$health_host" == "0.0.0.0" ]]; then
    health_host="127.0.0.1"
  fi

  for ((i=1; i<=START_TIMEOUT; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi

    if command -v curl >/dev/null 2>&1; then
      if curl -fsS --max-time 2 "http://${health_host}:${PORT}/api/status" >/dev/null 2>&1; then
        return 0
      fi
    else
      # If curl is unavailable, rely on process alive check after a short grace period.
      if (( i >= 3 )); then
        return 0
      fi
    fi

    sleep 1
  done

  return 1
}

main() {
  local current_pid
  current_pid="$(find_running_pid)"

  if [[ -n "$current_pid" ]]; then
    log "Service is already running, will restart."
    stop_pid "$current_pid"
  else
    log "Service is not running, will start a new instance."
  fi

  rm -f "$PID_FILE"
  build_start_cmd

  log "Starting service: ${START_CMD[*]}"
  nohup "${START_CMD[@]}" >> "$LOG_FILE" 2>&1 &
  local new_pid=$!
  echo "$new_pid" > "$PID_FILE"

  if wait_until_healthy "$new_pid"; then
    log "Service started successfully."
    log "PID: $new_pid"
    log "URL: http://127.0.0.1:${PORT}"
    log "Log: $LOG_FILE"
    exit 0
  fi

  log "Service failed to become healthy. Showing last logs:"
  tail -n 40 "$LOG_FILE" || true
  exit 1
}

main "$@"

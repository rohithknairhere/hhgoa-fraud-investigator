#!/usr/bin/env bash
# One-shot bootstrap for the HHGOA Agentic Fraud Investigation stack.
#
#   ./run.sh            install → test → benchmark → build → verify → serve
#   ./run.sh --serve    skip checks, just (re)start the servers
#   ./run.sh --check    everything except starting the servers (CI mode)
#
# Env (optional): TG_HOST/TG_USERNAME/TG_PASSWORD/TG_SECRET for a live TigerGraph
# (falls back to the deterministic mock when unset/unreachable), AGENT_PLANNER=claude
# with ANTHROPIC_API_KEY for the Claude evidence planner, SSL_CERTFILE/SSL_KEYFILE to
# serve the API over TLS directly, BACKEND_PORT (8000), FRONTEND_PORT (3000).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-all}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
export NEXT_TELEMETRY_DISABLED=1

log() { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }

PYTHON_BIN="$(command -v python3 || command -v python)"
VENV="$ROOT/backend/.venv"
if [[ -x "$VENV/bin/python" ]]; then VPY="$VENV/bin/python"; else VPY="$VENV/Scripts/python"; fi

setup_backend() {
  if [[ ! -d "$VENV" ]]; then
    log "Creating Python virtualenv"
    "$PYTHON_BIN" -m venv "$VENV"
    if [[ -x "$VENV/bin/python" ]]; then VPY="$VENV/bin/python"; else VPY="$VENV/Scripts/python"; fi
  fi
  log "Installing backend dependencies"
  "$VPY" -m pip install -q --upgrade pip
  "$VPY" -m pip install -q -r "$ROOT/backend/requirements.txt"
}

setup_frontend() {
  log "Installing frontend dependencies"
  (cd "$ROOT/frontend" && { [[ -f package-lock.json ]] && npm ci --no-audit --no-fund || npm install --no-audit --no-fund; })
}

checks() {
  log "Backend tests (pytest)"
  (cd "$ROOT/backend" && "$VPY" -m pytest -q)

  log "Running the 20 HHGOA benchmark cases"
  (cd "$ROOT/backend" && "$VPY" run_benchmarks.py --out "$ROOT/benchmark_results")

  log "Exporting TigerGraph loading CSVs"
  (cd "$ROOT/backend" && "$VPY" scripts/export_tigergraph_csv.py --out "$ROOT/tigergraph/data")

  # The backend is not running yet, so pages prerender from the snapshot; BACKEND_API_URL is read at runtime.
  log "Frontend typecheck, lint and production build"
  (cd "$ROOT/frontend" && npm run typecheck && npm run lint && npm run build)

  log "Contrast, broken-link and bundle-secret verification"
  (cd "$ROOT/frontend" && BACKEND_API_URL="http://127.0.0.1:$BACKEND_PORT" npm run verify)
}

serve() {
  local tls_args=()
  if [[ -n "${SSL_CERTFILE:-}" && -n "${SSL_KEYFILE:-}" ]]; then
    tls_args=(--ssl-certfile "$SSL_CERTFILE" --ssl-keyfile "$SSL_KEYFILE")
  fi
  [[ -d "$ROOT/frontend/.next" ]] || (cd "$ROOT/frontend" && npm run build)

  log "Starting FastAPI on :$BACKEND_PORT (HTTPS enforced; loopback exempt for local dev)"
  (cd "$ROOT/backend" && ENFORCE_HTTPS=true ALLOW_LOCAL_HTTP=true \
     FRONTEND_ORIGIN="https://localhost:$FRONTEND_PORT" \
     "$VPY" -m uvicorn app.api.main:app --host 127.0.0.1 --port "$BACKEND_PORT" ${tls_args[@]+"${tls_args[@]}"}) &
  BACK_PID=$!

  log "Starting Next.js on :$FRONTEND_PORT"
  (cd "$ROOT/frontend" && BACKEND_API_URL="http://127.0.0.1:$BACKEND_PORT" npx next start -p "$FRONTEND_PORT") &
  FRONT_PID=$!

  trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT INT TERM
  printf '\n  Dashboard  http://localhost:%s\n  API docs   http://127.0.0.1:%s/api/docs\n\n' "$FRONTEND_PORT" "$BACKEND_PORT"
  wait
}

case "$MODE" in
  --serve) serve ;;
  --check) setup_backend; setup_frontend; checks ;;
  all|*) setup_backend; setup_frontend; checks; serve ;;
esac

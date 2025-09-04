#!/usr/bin/env bash
# macOS launcher for Portfolio Manager (Automator-friendly)
# - loads and exports .env variables with explicit environment passing
# - starts the project's virtualenv (if present)
# - launches Streamlit with guaranteed environment inheritance
# - writes logs to ./logs/streamlit.out

set -euo pipefail

# Resolve project root (repo root) relative to this script
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# If a template .env exists but no .env, copy it (safe no-overwrite)
if [ ! -f ".env" ] && [ -f ".env.template" ]; then
  cp .env.template .env || true
fi

# 1) Load and export .env variables if present (so Streamlit inherits them)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

# 2) Prefer project virtualenv Python if available
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"
else
  PYTHON_EXEC="$(command -v python3 || true)"
  if [ -z "$PYTHON_EXEC" ]; then
    echo "Error: python3 not found. Install Python 3.11+ or create a virtualenv at .venv." >&2
    exit 1
  fi
fi

# 3) If Streamlit already running for this project, open the UI and exit
if pgrep -f "streamlit run .*app.py" >/dev/null 2>&1; then
  open "http://localhost:8502"
  exit 0
fi

# 4) Ensure log directory
mkdir -p logs
LOG_FILE="$PROJECT_DIR/logs/streamlit.out"

# 5) Prepare environment for Streamlit (explicit export to guarantee inheritance)
export APP_ENV="${APP_ENV:-production}"
export FINNHUB_API_KEY="${FINNHUB_API_KEY:-}"
export ENABLE_MICRO_PROVIDERS="${ENABLE_MICRO_PROVIDERS:-1}"

# 6) Start Streamlit in background with explicit environment passing
# Use nohup so the process survives Automator/launcher exit
nohup env \
    APP_ENV="$APP_ENV" \
    FINNHUB_API_KEY="$FINNHUB_API_KEY" \
    ENABLE_MICRO_PROVIDERS="$ENABLE_MICRO_PROVIDERS" \
    "$PYTHON_EXEC" -m streamlit run "$PROJECT_DIR/app.py" \
    --server.headless true \
    --server.port 8502 \
    --server.address localhost \
    > "$LOG_FILE" 2>&1 &

# 7) Give server a moment then open browser
sleep 2
open "http://localhost:8502"

exit 0

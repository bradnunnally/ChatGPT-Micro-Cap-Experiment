#!/usr/bin/env bash
# macOS launcher for Portfolio Manager (Automator-friendly)
# - starts the project's virtualenv (if present)
# - launches Streamlit in the background and opens the browser
# - writes logs to ./logs/streamlit.out

set -euo pipefail

REPO_DIR="/Users/bradnunnally/ChatGPT-Micro-Cap-Experiment"
cd "${REPO_DIR}"

# Ensure .env exists (do not overwrite if present)
if [ ! -f ".env" ] && [ -f ".env.template" ]; then
  cp .env.template .env || true
fi

# Prefer project virtualenv if available
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  PYTHON_EXEC="${REPO_DIR}/.venv/bin/python"
else
  # fall back to system python3
  PYTHON_EXEC="$(command -v python3 || true)"
  if [ -z "${PYTHON_EXEC}" ]; then
    echo "Error: python3 not found. Install Python 3.11+ or create a virtualenv at .venv." >&2
    exit 1
  fi
fi

# If Streamlit already running for this project, open the UI and exit
if pgrep -f "streamlit run .*app.py" >/dev/null 2>&1; then
  open "http://localhost:8501"
  exit 0
fi

# Ensure log directory
mkdir -p logs
LOG_FILE="${REPO_DIR}/logs/streamlit.out"

# Start Streamlit in background (detached)
nohup "${PYTHON_EXEC}" -m streamlit run "${REPO_DIR}/app.py" --server.headless true --server.port 8501 --server.address localhost > "${LOG_FILE}" 2>&1 &

# Give server a moment then open browser
sleep 2
open "http://localhost:8501"

exit 0

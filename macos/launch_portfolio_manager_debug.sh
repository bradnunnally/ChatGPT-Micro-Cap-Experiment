#!/usr/bin/env bash
# Enhanced macOS launcher for Portfolio Manager (Automator-friendly with debugging)
# - loads and exports .env variables with validation
# - starts the project's virtualenv (if present)
# - launches Streamlit with explicit environment passing
# - writes comprehensive logs for troubleshooting

set -euo pipefail

# Resolve project root (repo root) relative to this script
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# Create logs directory early
mkdir -p logs
DEBUG_LOG="$PROJECT_DIR/logs/launcher_debug.log"

# Function to log with timestamp
log_debug() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$DEBUG_LOG"
}

log_debug "=== Portfolio Manager Launcher Debug ==="
log_debug "Project Directory: $PROJECT_DIR"
log_debug "Current Working Directory: $(pwd)"
log_debug "Shell: $SHELL"
log_debug "User: $USER"

# If a template .env exists but no .env, copy it (safe no-overwrite)
if [ ! -f ".env" ] && [ -f ".env.template" ]; then
    cp .env.template .env || true
    log_debug "Copied .env.template to .env"
fi

# Check for .env file
if [ -f ".env" ]; then
    log_debug "Found .env file, loading variables..."
    
    # Load and export .env variables
    set -a
    # shellcheck disable=SC1091
    source ".env"
    set +a
    
    # Verify critical environment variables (without exposing values)
    if [ -n "${APP_ENV:-}" ]; then
        log_debug "APP_ENV is set to: $APP_ENV"
    else
        log_debug "WARNING: APP_ENV is not set"
    fi
    
    if [ -n "${FINNHUB_API_KEY:-}" ]; then
        log_debug "FINNHUB_API_KEY is set (length: ${#FINNHUB_API_KEY})"
    else
        log_debug "WARNING: FINNHUB_API_KEY is not set"
    fi
else
    log_debug "WARNING: No .env file found"
fi

# Prefer project virtualenv Python if available
if [ -f ".venv/bin/activate" ]; then
    log_debug "Activating project virtualenv..."
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
    PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"
    log_debug "Using virtualenv Python: $PYTHON_EXEC"
else
    PYTHON_EXEC="$(command -v python3 || true)"
    if [ -z "$PYTHON_EXEC" ]; then
        log_debug "ERROR: python3 not found"
        echo "Error: python3 not found. Install Python 3.11+ or create a virtualenv at .venv." >&2
        exit 1
    fi
    log_debug "Using system Python: $PYTHON_EXEC"
fi

# Verify Python executable
if [ -x "$PYTHON_EXEC" ]; then
    PYTHON_VERSION=$("$PYTHON_EXEC" --version 2>&1)
    log_debug "Python version: $PYTHON_VERSION"
else
    log_debug "ERROR: Python executable not found or not executable: $PYTHON_EXEC"
    exit 1
fi

# Check if Streamlit is already running
EXISTING_STREAMLIT=$(pgrep -f "streamlit run .*app.py" || true)
if [ -n "$EXISTING_STREAMLIT" ]; then
    log_debug "Streamlit already running (PID: $EXISTING_STREAMLIT), opening browser..."
    open "http://localhost:8502"
    exit 0
fi

# Prepare environment for Streamlit (explicit export)
export APP_ENV="${APP_ENV:-production}"
export FINNHUB_API_KEY="${FINNHUB_API_KEY:-}"
export ENABLE_MICRO_PROVIDERS="${ENABLE_MICRO_PROVIDERS:-1}"

log_debug "Starting Streamlit with environment:"
log_debug "  APP_ENV=$APP_ENV"
log_debug "  FINNHUB_API_KEY=${FINNHUB_API_KEY:+***SET***}"
log_debug "  ENABLE_MICRO_PROVIDERS=$ENABLE_MICRO_PROVIDERS"

# Ensure log directory
LOG_FILE="$PROJECT_DIR/logs/streamlit.out"

# Start Streamlit in background with explicit environment passing
log_debug "Starting Streamlit process..."
nohup env \
    APP_ENV="$APP_ENV" \
    FINNHUB_API_KEY="$FINNHUB_API_KEY" \
    ENABLE_MICRO_PROVIDERS="$ENABLE_MICRO_PROVIDERS" \
    "$PYTHON_EXEC" -m streamlit run "$PROJECT_DIR/app.py" \
    --server.headless true \
    --server.port 8502 \
    --server.address localhost \
    > "$LOG_FILE" 2>&1 &

STREAMLIT_PID=$!
log_debug "Streamlit started with PID: $STREAMLIT_PID"

# Give server a moment to start
sleep 3

# Verify Streamlit is still running
if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
    log_debug "Streamlit process is running successfully"
    open "http://localhost:8502"
    log_debug "Browser opened to http://localhost:8502"
else
    log_debug "ERROR: Streamlit process failed to start or crashed"
    log_debug "Check logs at: $LOG_FILE"
    exit 1
fi

log_debug "=== Launcher completed successfully ==="
exit 0

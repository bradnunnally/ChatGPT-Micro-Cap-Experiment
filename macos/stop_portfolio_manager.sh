#!/usr/bin/env bash
# Stop Portfolio Manager Streamlit processes

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEBUG_LOG="$PROJECT_DIR/logs/launcher_debug.log"

# Function to log with timestamp
log_debug() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$DEBUG_LOG"
}

log_debug "=== Stopping Portfolio Manager ==="

# Find and stop all Streamlit processes (any port)
STREAMLIT_PIDS=$(pgrep -f "streamlit" || true)

if [ -z "$STREAMLIT_PIDS" ]; then
    log_debug "No Streamlit processes found running"
    echo "No Portfolio Manager processes are currently running."
else
    log_debug "Found Streamlit processes: $STREAMLIT_PIDS"
    echo "Stopping Portfolio Manager processes..."
    
    for pid in $STREAMLIT_PIDS; do
        log_debug "Killing PID: $pid"
        kill "$pid" 2>/dev/null || true
        sleep 1
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            log_debug "Force killing PID: $pid"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    echo "Portfolio Manager stopped successfully."
fi

# Also kill any processes using ports 8501 or 8502
for port in 8501 8502; do
    PORT_PID=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PORT_PID" ]; then
        log_debug "Killing process on port $port (PID: $PORT_PID)"
        kill "$PORT_PID" 2>/dev/null || true
        sleep 1
        if kill -0 "$PORT_PID" 2>/dev/null; then
            kill -9 "$PORT_PID" 2>/dev/null || true
        fi
    fi
done

log_debug "=== Stop completed ==="

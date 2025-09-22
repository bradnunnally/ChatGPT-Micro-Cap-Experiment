#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
APP_NAME="Portfolio Manager"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
RESOURCES_APP_DIR="$RESOURCES_DIR/app"
RESOURCES_VENV_DIR="$RESOURCES_DIR/venv"

# Allow VERSION env override, otherwise derive from git or timestamp
VERSION="${VERSION:-$(git -C "$PROJECT_DIR" describe --tags --always 2>/dev/null || date +%Y%m%d%H%M)}"
CURRENT_YEAR="$(date +%Y)"

if [ ! -x "$PROJECT_DIR/.venv/bin/python3" ]; then
  echo "Virtual environment not found at $PROJECT_DIR/.venv. Run 'make install' first." >&2
  exit 1
fi

mkdir -p "$DIST_DIR"
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

RSYNC_EXCLUDES=(
  "--exclude" ".git"
  "--exclude" ".mypy_cache"
  "--exclude" ".pytest_cache"
  "--exclude" "__pycache__"
  "--exclude" "dist"
  "--exclude" ".venv"
  "--exclude" "logs"
  "--exclude" "*.log"
  "--exclude" ".DS_Store"
  "--exclude" "*.pyc"
  "--exclude" ".coverage"
  "--exclude" "htmlcov"
  "--exclude" ".env"
)

rsync -a "${RSYNC_EXCLUDES[@]}" "$PROJECT_DIR/" "$RESOURCES_APP_DIR/"

rsync -a "$PROJECT_DIR/.venv/" "$RESOURCES_VENV_DIR/"

# Prune compiled artefacts from bundled source to reduce size
find "$RESOURCES_APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$RESOURCES_APP_DIR" -name '*.pyc' -delete

cat >"$CONTENTS_DIR/Info.plist" <<EOF2
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.chatgpt.microcap.portfolio-manager</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleExecutable</key>
    <string>PortfolioManager</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © $CURRENT_YEAR Portfolio Manager</string>
</dict>
</plist>
EOF2

cat >"$MACOS_DIR/PortfolioManager" <<'EOF2'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_SOURCE_DIR="$RESOURCES_DIR/app"
VENV_DIR="$RESOURCES_DIR/venv"
PYTHON_EXEC="$VENV_DIR/bin/python3"

if [ ! -x "$PYTHON_EXEC" ]; then
  echo "Embedded Python runtime missing at $PYTHON_EXEC" >&2
  exit 1
fi

SUPPORT_ROOT="$HOME/Library/Application Support/PortfolioManager"
RUNTIME_DIR="$SUPPORT_ROOT/runtime"
DATA_RUNTIME_DIR="$RUNTIME_DIR/data"
STREAMLIT_RUNTIME_DIR="$RUNTIME_DIR/.streamlit"
LOG_DIR="$HOME/Library/Logs/PortfolioManager"
VERSION_FILE="$RESOURCES_DIR/VERSION"
BUNDLE_VERSION="dev"

mkdir -p "$SUPPORT_ROOT" "$RUNTIME_DIR" "$LOG_DIR"

if [ -f "$VERSION_FILE" ]; then
  BUNDLE_VERSION="$(cat "$VERSION_FILE")"
fi

echo "$BUNDLE_VERSION" >"$SUPPORT_ROOT/BUNDLE_VERSION"

if [ -d "$APP_SOURCE_DIR/data" ]; then
  if [ ! -d "$DATA_RUNTIME_DIR" ]; then
    mkdir -p "$DATA_RUNTIME_DIR"
    rsync -a "$APP_SOURCE_DIR/data/" "$DATA_RUNTIME_DIR/"
  else
    if ! compgen -G "$DATA_RUNTIME_DIR/*" > /dev/null; then
      rsync -a "$APP_SOURCE_DIR/data/" "$DATA_RUNTIME_DIR/"
    fi
  fi
fi

if [ -d "$APP_SOURCE_DIR/.streamlit" ] && [ ! -d "$STREAMLIT_RUNTIME_DIR" ]; then
  mkdir -p "$STREAMLIT_RUNTIME_DIR"
  rsync -a "$APP_SOURCE_DIR/.streamlit/" "$STREAMLIT_RUNTIME_DIR/"
fi

if [ ! -f "$RUNTIME_DIR/.env" ]; then
  if [ -f "$APP_SOURCE_DIR/.env.template" ]; then
    cp "$APP_SOURCE_DIR/.env.template" "$RUNTIME_DIR/.env"
  elif [ -f "$APP_SOURCE_DIR/.env.example" ]; then
    cp "$APP_SOURCE_DIR/.env.example" "$RUNTIME_DIR/.env"
  fi
fi

if [ -f "$RUNTIME_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_DIR/.env"
  set +a
fi

export APP_ENV=production
export APP_BASE_DIR="$RUNTIME_DIR"
export ENABLE_MICRO_PROVIDERS="${ENABLE_MICRO_PROVIDERS:-1}"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

LOG_FILE="$LOG_DIR/streamlit.out"

if pgrep -f "streamlit run .*app.py" >/dev/null 2>&1; then
  open "http://localhost:8502"
  exit 0
fi

cd "$APP_SOURCE_DIR"

nohup env \
    APP_ENV="$APP_ENV" \
    APP_BASE_DIR="$APP_BASE_DIR" \
    FINNHUB_API_KEY="${FINNHUB_API_KEY:-}" \
    ENABLE_MICRO_PROVIDERS="$ENABLE_MICRO_PROVIDERS" \
    "$PYTHON_EXEC" -m streamlit run "$APP_SOURCE_DIR/app.py" \
    --server.headless true \
    --server.port 8502 \
    --server.address localhost \
    >"$LOG_FILE" 2>&1 &

sleep 2
open "http://localhost:8502"
EOF2

chmod +x "$MACOS_DIR/PortfolioManager"

echo "$VERSION" >"$RESOURCES_DIR/VERSION"

echo "Built $APP_BUNDLE"

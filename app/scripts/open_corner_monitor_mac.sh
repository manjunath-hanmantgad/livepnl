#!/usr/bin/env bash
set -euo pipefail

# Starts compact Streamlit monitor and opens it in a Chrome app window at bottom-right.
# macOS only.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "Missing .venv in $ROOT_DIR"
  exit 1
fi

source .venv/bin/activate

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8010}"
PORT="${CORNER_PORT:-8503}"

nohup env API_BASE_URL="$API_BASE_URL" streamlit run app/ui/streamlit_compact.py --server.port "$PORT" >/tmp/livepnl-corner.log 2>&1 &
sleep 2

URL="http://127.0.0.1:${PORT}"

# Chrome app-mode window; manual Always On Top can be enabled from window manager tools.
open -na "Google Chrome" --args --app="$URL" --window-size=380,420 --window-position=1540,730

echo "Corner monitor started at $URL"
echo "If needed, adjust window position/size in this script for your screen resolution."

#!/bin/bash
# Auto SessionStart Hook
# Starts Context Engine automatically on every Claude Code session start.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${PROJECT_MEMORY_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

# Keep hook output quiet; write diagnostics to a dedicated hook log.
mkdir -p "$MEMORY_DIR/.logs"
python3 "$MEMORY_DIR/scripts/service_manager.py" autostart --no-browser \
  >>"$MEMORY_DIR/.logs/hook_autostart.log" 2>&1 || true

exit 0

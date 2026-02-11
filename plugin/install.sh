#!/usr/bin/env bash
set -euo pipefail

# Context Engine plugin installer for Claude Code.
# Can be run from a local clone or via curl from GitHub.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_CANDIDATES=(
  "$(cd "$SCRIPT_DIR/.." && pwd)"
  "$(cd "$SCRIPT_DIR/../.." && pwd)"
)
REPO_ROOT=""
for candidate in "${ROOT_CANDIDATES[@]}"; do
  if [[ -f "$candidate/ce" && -d "$candidate/scripts" ]]; then
    REPO_ROOT="$candidate"
    break
  fi
done

DEFAULT_REPO_URL="https://github.com/onethousand-ai/context-engine.git"
REPO_URL="${CE_REPO_URL:-$DEFAULT_REPO_URL}"
REF="${CE_REF:-main}"
INSTALL_BASE="${CE_INSTALL_BASE:-$HOME/.claude/plugins}"
INSTALL_DIR="$INSTALL_BASE/context-engine"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

mkdir -p "$INSTALL_BASE"

if [[ -n "$REPO_ROOT" && -e "$REPO_ROOT/.git" && -f "$REPO_ROOT/ce" && -d "$REPO_ROOT/scripts" ]]; then
  # Running from repository checkout.
  if [[ "$REPO_ROOT" != "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    cp -R "$REPO_ROOT" "$INSTALL_DIR"
  fi
else
  # Running standalone (e.g., curl pipe) -> clone from GitHub.
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" fetch origin "$REF"
    git -C "$INSTALL_DIR" checkout "$REF"
    git -C "$INSTALL_DIR" pull --ff-only origin "$REF"
  else
    rm -rf "$INSTALL_DIR"
    git clone --branch "$REF" --single-branch "$REPO_URL" "$INSTALL_DIR"
  fi
fi

# Resolve Context Engine root inside install dir.
if [[ -f "$INSTALL_DIR/ce" && -d "$INSTALL_DIR/scripts" ]]; then
  CE_ROOT="$INSTALL_DIR"
elif [[ -f "$INSTALL_DIR/sydney/ce" && -d "$INSTALL_DIR/sydney/scripts" ]]; then
  CE_ROOT="$INSTALL_DIR/sydney"
else
  echo "Could not find Context Engine root in $INSTALL_DIR"
  exit 1
fi

chmod +x "$CE_ROOT/ce" "$CE_ROOT/scripts/hooks_AutoSessionStart.sh"
python3 "$CE_ROOT/scripts/setup_hooks.py" --force

echo ""
echo "Context Engine plugin installed."
echo "Install dir: $INSTALL_DIR"
echo "Claude hooks configured for automatic SessionStart invocation."
echo ""
echo "Test:"
echo "  bash $CE_ROOT/scripts/hooks_AutoSessionStart.sh"
echo "  $CE_ROOT/ce status"

#!/usr/bin/env bash
set -euo pipefail

INSTALL_BASE="${CE_INSTALL_BASE:-$HOME/.claude/plugins}"
INSTALL_DIR="$INSTALL_BASE/context-engine"
REMOVE_FILES="${CE_REMOVE_FILES:-false}"

if [[ -f "$INSTALL_DIR/scripts/setup_hooks.py" ]]; then
  CE_ROOT="$INSTALL_DIR"
elif [[ -f "$INSTALL_DIR/sydney/scripts/setup_hooks.py" ]]; then
  CE_ROOT="$INSTALL_DIR/sydney"
else
  CE_ROOT=""
fi

if [[ -n "$CE_ROOT" ]]; then
  python3 "$CE_ROOT/scripts/setup_hooks.py" --remove || true
fi

if [[ "$REMOVE_FILES" == "true" ]]; then
  rm -rf "$INSTALL_DIR"
  echo "Removed $INSTALL_DIR"
else
  echo "Hooks removed. Files kept at $INSTALL_DIR"
  echo "To remove files too:"
  if [[ -n "$CE_ROOT" ]]; then
    echo "  CE_REMOVE_FILES=true bash $CE_ROOT/plugin/uninstall.sh"
  else
    echo "  CE_REMOVE_FILES=true bash $INSTALL_DIR/plugin/uninstall.sh"
  fi
fi

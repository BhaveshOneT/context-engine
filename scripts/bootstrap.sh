#!/usr/bin/env bash
# Context Engine Bootstrap
# One-command setup: dependencies, hooks, registry, embeddings

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CE_PYTHON:-python3}"

SKIP_DEPS=false
SKIP_OPTIONAL_DEPS=false
SKIP_HOOKS=false
SKIP_REGISTRY=false
SKIP_EMBEDDINGS=false
MINIMAL=false

usage() {
  echo "Context Engine Bootstrap"
  echo ""
  echo "Usage: ./ce setup [options]"
  echo ""
  echo "Options:"
  echo "  --minimal            Install only core deps (watchdog, flask)"
  echo "  --skip-deps          Skip dependency installation"
  echo "  --skip-optional-deps Skip optional deps (embeddings + TLDR)"
  echo "  --skip-hooks         Skip Claude Code hook setup"
  echo "  --skip-registry      Skip session registry init"
  echo "  --skip-embeddings    Skip embedding generation"
  echo "  --help               Show this help"
  echo ""
  echo "Environment:"
  echo "  CE_PYTHON=python3           Override python binary"
  echo "  CE_BOOTSTRAP_PIP_ARGS=\"...\" Extra args passed to pip"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --minimal)
      MINIMAL=true
      SKIP_EMBEDDINGS=true
      ;;
    --skip-deps)
      SKIP_DEPS=true
      ;;
    --skip-optional-deps)
      SKIP_OPTIONAL_DEPS=true
      ;;
    --skip-hooks)
      SKIP_HOOKS=true
      ;;
    --skip-registry)
      SKIP_REGISTRY=true
      ;;
    --skip-embeddings)
      SKIP_EMBEDDINGS=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found"
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "Error: pip not available for $PYTHON_BIN"
  echo "Install pip first, then re-run ./ce setup"
  exit 1
fi

BASE_DEPS=(watchdog flask)
OPTIONAL_DEPS=(sentence-transformers numpy tree-sitter tree-sitter-languages)

PIP_ARGS=()
if [ -z "${VIRTUAL_ENV:-}" ]; then
  PIP_ARGS+=(--user)
fi

if [ -n "${CE_BOOTSTRAP_PIP_ARGS:-}" ]; then
  read -r -a EXTRA_PIP_ARGS <<< "${CE_BOOTSTRAP_PIP_ARGS}"
  PIP_ARGS+=("${EXTRA_PIP_ARGS[@]}")
fi

echo "==============================================="
echo "Context Engine Bootstrap"
echo "==============================================="

if [ "$SKIP_DEPS" = false ]; then
  echo ""
  echo "Step 1/4: Installing dependencies..."
  if [ "$MINIMAL" = true ] || [ "$SKIP_OPTIONAL_DEPS" = true ]; then
    "$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" "${BASE_DEPS[@]}"
  else
    "$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" "${BASE_DEPS[@]}" "${OPTIONAL_DEPS[@]}"
  fi
else
  echo ""
  echo "Step 1/4: Skipping dependency installation"
fi

if [ "$SKIP_HOOKS" = false ]; then
  echo ""
  echo "Step 2/4: Configuring Claude Code hooks..."
  "$PYTHON_BIN" "$CE_ROOT/scripts/setup_hooks.py" --force
else
  echo ""
  echo "Step 2/4: Skipping hook setup"
fi

if [ "$SKIP_REGISTRY" = false ]; then
  echo ""
  echo "Step 3/4: Initializing session registry..."
  "$PYTHON_BIN" "$CE_ROOT/scripts/session-registry.py" init
else
  echo ""
  echo "Step 3/4: Skipping session registry init"
fi

if [ "$SKIP_EMBEDDINGS" = false ]; then
  echo ""
  echo "Step 4/4: Generating embeddings (semantic search)..."
  "$PYTHON_BIN" "$CE_ROOT/scripts/vector-search.py" --generate
else
  echo ""
  echo "Step 4/4: Skipping embedding generation"
fi

echo ""
echo "✅ Bootstrap complete."
echo "Next: ./ce activate"

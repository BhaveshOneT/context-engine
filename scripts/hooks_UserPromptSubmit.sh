#!/bin/bash
# UserPromptSubmit Hook - Captures user requests before processing
# Triggered when user submits a prompt to Claude Code
#
# This hook records user prompts for:
# - Session continuity (what did user originally ask for?)
# - Structured summaries (request field)
# - Prompt history across sessions
#
# Inspired by claude-mem's UserPromptSubmit hook.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${PROJECT_MEMORY_DIR:-$(dirname "$SCRIPT_DIR")}"

# Get prompt text from environment or stdin
# Claude Code passes the prompt in PROMPT or CLAUDE_PROMPT or via stdin
PROMPT_TEXT="${PROMPT:-${CLAUDE_PROMPT:-}}"

# If no environment variable, try reading from stdin (non-blocking)
if [ -z "$PROMPT_TEXT" ]; then
    # Read from argument if provided
    if [ -n "$1" ]; then
        PROMPT_TEXT="$1"
    fi
fi

# Fallback to stdin if provided
if [ -z "$PROMPT_TEXT" ]; then
    if [ ! -t 0 ]; then
        PROMPT_TEXT="$(cat)"
    fi
fi

# Only proceed if we have prompt text
if [ -z "$PROMPT_TEXT" ]; then
    # Silent exit - no prompt to record
    exit 0
fi

# Record the prompt using Python tracker
if command -v python3 &> /dev/null && [ -f "$SCRIPT_DIR/prompt_tracker.py" ]; then
    python3 "$SCRIPT_DIR/prompt_tracker.py" record "$PROMPT_TEXT" 2>/dev/null || true
fi

# Optional: Show brief confirmation (can be disabled for cleaner output)
# echo "📝 Prompt recorded"

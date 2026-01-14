#!/bin/bash
# PreToolUse Hook - Shows current plan before actions
# Helps agent stay oriented during long sessions

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"

# Only show plan for certain tools (Write, Edit, Bash commands)
# This prevents excessive output during simple reads

# Check if active task plan exists
if [ -f "$MEMORY_DIR/active/task_plan.md" ]; then
    echo "════════════════════════════════════════════════════"
    echo "  📋 CURRENT TASK PLAN (Quick Refresh)"
    echo "════════════════════════════════════════════════════"

    # Show goal
    echo ""
    echo "🎯 GOAL:"
    sed -n '/^## Goal/,/^##/p' "$MEMORY_DIR/active/task_plan.md" | grep -v "^##" | head -3

    # Show current phases
    echo ""
    echo "📊 PHASES:"
    grep "^- \[" "$MEMORY_DIR/active/task_plan.md" | head -8

    # Show recent errors (if any)
    if grep -q "|.*|.*|" "$MEMORY_DIR/active/task_plan.md"; then
        echo ""
        echo "⚠️  ERRORS THIS SESSION:"
        grep "|" "$MEMORY_DIR/active/task_plan.md" | grep -v "^| Error |" | tail -3
    fi

    echo ""
    echo "════════════════════════════════════════════════════"
    echo ""
fi

# Reminder: Check failures.md before attempting risky operations
TOOL_NAME="${1:-unknown}"
if [[ "$TOOL_NAME" =~ (Bash|Execute|Run) ]]; then
    if [ -f "$MEMORY_DIR/knowledge/failures.md" ]; then
        # Check if there are known failures
        FAILURE_COUNT=$(grep -c "^## Error:\|^## Anti-Pattern:" "$MEMORY_DIR/knowledge/failures.md" 2>/dev/null || echo "0")
        if [ "$FAILURE_COUNT" -gt 0 ]; then
            echo "💡 TIP: Check knowledge/failures.md for known errors before executing"
        fi
    fi
fi

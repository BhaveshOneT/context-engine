#!/bin/bash
# SessionEnd Hook - Checks if knowledge was updated
# Ensures learnings don't get lost

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"

echo ""
echo "════════════════════════════════════════════════════"
echo "  🏁 SESSION ENDING - Knowledge Check"
echo "════════════════════════════════════════════════════"
echo ""

# Check if knowledge base was updated this session
if [ -d "$MEMORY_DIR/knowledge" ]; then
    echo "📊 Checking for knowledge updates..."

    # Use git to check if knowledge files changed (if in git repo)
    if git rev-parse --git-dir > /dev/null 2>&1; then
        CHANGED=$(git diff --name-only "$MEMORY_DIR/knowledge/" 2>/dev/null || echo "")

        if [ -n "$CHANGED" ]; then
            echo "✅ Knowledge base updated:"
            echo "$CHANGED" | sed 's/^/     • /'
        else
            echo "⚠️  WARNING: No knowledge updates detected!"
            echo ""
            echo "   Did you document:"
            echo "   • New patterns discovered?"
            echo "   • Errors encountered?"
            echo "   • Decisions made?"
            echo "   • Gotchas found?"
            echo ""
            echo "   If not, update now before session ends!"
        fi
    else
        echo "ℹ️  Not a git repository - manual check recommended"
    fi
fi

# Remind to create handoff if task is complete
if [ -f "$MEMORY_DIR/active/task_plan.md" ]; then
    if grep -q "\[x\].*Phase.*complete" "$MEMORY_DIR/active/task_plan.md"; then
        echo ""
        echo "💡 Task appears complete. Remember to:"
        echo "   1. Create YAML handoff (handoffs/latest.yaml)"
        echo "   2. Archive active files (scripts/archive-task.sh)"
        echo "   3. Update knowledge index"
    fi
fi

echo ""
echo "════════════════════════════════════════════════════"
echo ""

#!/bin/bash
# PostToolUse Hook - Reminds to update knowledge after errors
# Helps capture learnings in real-time

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${PROJECT_MEMORY_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
EXIT_CODE="${1:-0}"

# If the previous command failed, remind to document it
if [ "$EXIT_CODE" -ne 0 ]; then
    echo ""
    echo "════════════════════════════════════════════════════"
    echo "  ⚠️  ERROR DETECTED"
    echo "════════════════════════════════════════════════════"
    echo ""
    echo "📝 Remember to document this error:"
    echo ""
    echo "  1. Add to knowledge/failures.md immediately"
    echo "  2. Log in active/task_plan.md error table"
    echo "  3. Don't repeat the same action - mutate approach!"
    echo ""
    echo "Error Protocol:"
    echo "  • Attempt 1: Diagnose & fix"
    echo "  • Attempt 2: Alternative approach"
    echo "  • Attempt 3: Broader rethink"
    echo "  • After 3: Escalate to user"
    echo ""
    echo "════════════════════════════════════════════════════"
    echo ""
fi

# Reminder about 2-action rule for discoveries
# (This would need to track state, simplified version here)
if [ -f "$MEMORY_DIR/active/context.md" ]; then
    # Count recent additions (simplified - checks file modification time)
    LAST_UPDATED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$MEMORY_DIR/active/context.md" 2>/dev/null || echo "unknown")
    echo "💡 Last context update: $LAST_UPDATED"
    echo "   (Remember: Save findings after every 2 view/search operations)"
fi

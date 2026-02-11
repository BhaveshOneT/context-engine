#!/bin/bash
# Archive completed task and clean active directory
# Usage: ./archive-task.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${PROJECT_MEMORY_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ARCHIVE_DATE=$(date +%Y-%m-%d)

echo "════════════════════════════════════════════════════"
echo "  📦 Ultra-Planning V3: Archive Task"
echo "════════════════════════════════════════════════════"
echo ""

# Check if there's an active task
if [ ! -f "$MEMORY_DIR/active/task_plan.md" ]; then
    echo "❌ No active task found to archive"
    exit 1
fi

# V3: Call orchestrator for clean shutdown
if command -v python3 &> /dev/null && [ -f "$MEMORY_DIR/scripts/session-orchestrator.py" ]; then
    echo "🤖 Running V3 session cleanup..."
    echo ""
    python3 "$MEMORY_DIR/scripts/session-orchestrator.py" end
    echo ""
fi

# Extract task name from task_plan.md
TASK_NAME=$(grep "^# Task:" "$MEMORY_DIR/active/task_plan.md" | sed 's/# Task: //' | head -1 | tr ' ' '-' | tr '[:upper:]' '[:lower:]')

if [ -z "$TASK_NAME" ]; then
    TASK_NAME="unnamed-task"
fi

# Extract session id (if present)
SESSION_ID=$(grep -m1 "^\*\*Session ID:\*\*" "$MEMORY_DIR/active/task_plan.md" | sed -E 's/^\*\*Session ID:\*\* //')

ARCHIVE_DIR="$MEMORY_DIR/archive/${ARCHIVE_DATE}_${TASK_NAME}"

# Create archive directory
mkdir -p "$ARCHIVE_DIR"

echo "Archiving to: $ARCHIVE_DIR"
echo ""

# Move active files
if [ -f "$MEMORY_DIR/active/task_plan.md" ]; then
    mv "$MEMORY_DIR/active/task_plan.md" "$ARCHIVE_DIR/"
    echo "✓ Archived task_plan.md"
fi

if [ -f "$MEMORY_DIR/active/context.md" ]; then
    mv "$MEMORY_DIR/active/context.md" "$ARCHIVE_DIR/"
    echo "✓ Archived context.md"
fi

# Move continuity ledger
if [ -f "$MEMORY_DIR/ledgers/CONTINUITY_active.md" ]; then
    mv "$MEMORY_DIR/ledgers/CONTINUITY_active.md" "$ARCHIVE_DIR/CONTINUITY.md"
    echo "✓ Archived continuity ledger"
fi

# Archive prompt and durable event logs
if [ -f "$MEMORY_DIR/active/.prompts_log.yaml" ]; then
    mv "$MEMORY_DIR/active/.prompts_log.yaml" "$ARCHIVE_DIR/prompts.yaml"
    echo "✓ Archived prompts log"
fi

if [ -f "$MEMORY_DIR/active/.events.jsonl" ]; then
    mv "$MEMORY_DIR/active/.events.jsonl" "$ARCHIVE_DIR/events.jsonl"
    echo "✓ Archived durable event log"
fi

if [ -f "$MEMORY_DIR/active/.events_state.json" ]; then
    mv "$MEMORY_DIR/active/.events_state.json" "$ARCHIVE_DIR/events_state.json"
    echo "✓ Archived event replay state"
fi

# Archive handoff
if [ -f "$MEMORY_DIR/handoffs/latest.yaml" ]; then
    mkdir -p "$MEMORY_DIR/handoffs/archive"
    cp "$MEMORY_DIR/handoffs/latest.yaml" "$ARCHIVE_DIR/handoff.yaml"
    mv "$MEMORY_DIR/handoffs/latest.yaml" "$MEMORY_DIR/handoffs/archive/${ARCHIVE_DATE}_${TASK_NAME}.yaml"
    echo "✓ Archived handoff"
fi

# Update session registry
if [ -n "$SESSION_ID" ] && command -v python3 &> /dev/null && [ -f "$MEMORY_DIR/scripts/session-registry.py" ]; then
    ARCHIVED_HANDOFF="$MEMORY_DIR/handoffs/archive/${ARCHIVE_DATE}_${TASK_NAME}.yaml"
    if [ -f "$ARCHIVED_HANDOFF" ]; then
        python3 "$MEMORY_DIR/scripts/session-registry.py" end --id "$SESSION_ID" --handoff "$ARCHIVED_HANDOFF" --quiet || true
    else
        python3 "$MEMORY_DIR/scripts/session-registry.py" end --id "$SESSION_ID" --quiet || true
    fi
fi

# Create archive README
cat > "$ARCHIVE_DIR/README.md" << EOF
# Archived Task: $TASK_NAME

**Archived:** $ARCHIVE_DATE
**Session ID:** $(grep "Session ID:" "$ARCHIVE_DIR/task_plan.md" | cut -d: -f2 | xargs)

## Files

- \`task_plan.md\` - Task planning and phases
- \`context.md\` - Research and discoveries
- \`CONTINUITY.md\` - Session continuity ledger
- \`handoff.yaml\` - Session handoff (YAML format)

## Knowledge Extracted

Check these knowledge base files for learnings from this session:

- \`$MEMORY_DIR/knowledge/patterns.md\`
- \`$MEMORY_DIR/knowledge/failures.md\`
- \`$MEMORY_DIR/knowledge/decisions.md\`
- \`$MEMORY_DIR/knowledge/gotchas.md\`

## Restore

To review this archived task:

\`\`\`bash
cat "$ARCHIVE_DIR/task_plan.md"
cat "$ARCHIVE_DIR/context.md"
\`\`\`
EOF

echo "✓ Created archive README"

echo ""
echo "════════════════════════════════════════════════════"
echo "  ✅ Task archived successfully!"
echo "════════════════════════════════════════════════════"
echo ""
echo "Archive location: $ARCHIVE_DIR"
echo ""
echo "Active directory is now clean and ready for next task."
echo "Run: ./init-session.sh <task-name> to start new task"
echo ""

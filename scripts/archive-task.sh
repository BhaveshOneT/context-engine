#!/bin/bash
# Archive completed task and clean active directory
# Usage: ./archive-task.sh

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"
ARCHIVE_DATE=$(date +%Y-%m-%d)

echo "════════════════════════════════════════════════════"
echo "  📦 Ultra-Planning V2: Archive Task"
echo "════════════════════════════════════════════════════"
echo ""

# Check if there's an active task
if [ ! -f "$MEMORY_DIR/active/task_plan.md" ]; then
    echo "❌ No active task found to archive"
    exit 1
fi

# Extract task name from task_plan.md
TASK_NAME=$(grep "^# Task:" "$MEMORY_DIR/active/task_plan.md" | sed 's/# Task: //' | head -1 | tr ' ' '-' | tr '[:upper:]' '[:lower:]')

if [ -z "$TASK_NAME" ]; then
    TASK_NAME="unnamed-task"
fi

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

# Archive handoff
if [ -f "$MEMORY_DIR/handoffs/latest.yaml" ]; then
    cp "$MEMORY_DIR/handoffs/latest.yaml" "$ARCHIVE_DIR/handoff.yaml"
    mv "$MEMORY_DIR/handoffs/latest.yaml" "$MEMORY_DIR/handoffs/archive/${ARCHIVE_DATE}_${TASK_NAME}.yaml"
    echo "✓ Archived handoff"
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

- \`.project-memory/knowledge/patterns.md\`
- \`.project-memory/knowledge/failures.md\`
- \`.project-memory/knowledge/decisions.md\`
- \`.project-memory/knowledge/gotchas.md\`

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

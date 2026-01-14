#!/bin/bash
# SessionStart Hook - Loads knowledge before starting work
# Place this in your Claude hooks configuration

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"

echo "════════════════════════════════════════════════════"
echo "  📚 ULTRA-PLANNING V2: Loading Knowledge Base"
echo "════════════════════════════════════════════════════"

# Check if knowledge base exists
if [ ! -d "$MEMORY_DIR/knowledge" ]; then
    echo "⚠️  No knowledge base found. This might be your first session."
    echo "   Knowledge will be created as you work."
    exit 0
fi

# Display past learnings
if [ -f "$MEMORY_DIR/knowledge/patterns.md" ]; then
    echo ""
    echo "✓ SUCCESSFUL PATTERNS (Past Learnings):"
    echo "────────────────────────────────────────"
    # Extract pattern names (lines starting with ## Pattern:)
    grep "^## Pattern:" "$MEMORY_DIR/knowledge/patterns.md" | head -5 | sed 's/^##/  •/'

    # Count total patterns
    PATTERN_COUNT=$(grep -c "^## Pattern:" "$MEMORY_DIR/knowledge/patterns.md" 2>/dev/null || echo "0")
    echo "  📊 Total patterns: $PATTERN_COUNT"
fi

# Display known failures (errors to avoid)
if [ -f "$MEMORY_DIR/knowledge/failures.md" ]; then
    echo ""
    echo "⚠️  KNOWN FAILURES (Avoid These):"
    echo "────────────────────────────────────────"
    grep "^## " "$MEMORY_DIR/knowledge/failures.md" | grep -v "^## How\|^## Failure\|^## Anti-Pattern Template" | head -5 | sed 's/^##/  •/'

    FAILURE_COUNT=$(grep -c "^## Error:\|^## Anti-Pattern:" "$MEMORY_DIR/knowledge/failures.md" 2>/dev/null || echo "0")
    echo "  📊 Total documented errors: $FAILURE_COUNT"
fi

# Load latest handoff if exists
if [ -f "$MEMORY_DIR/handoffs/latest.yaml" ]; then
    echo ""
    echo "🔄 PREVIOUS SESSION CONTEXT:"
    echo "────────────────────────────────────────"
    # Extract key info from YAML
    grep "^task:\|^status:\|^next_session_hints:" "$MEMORY_DIR/handoffs/latest.yaml" | head -10 | sed 's/^/  /'
fi

# Show knowledge base statistics
echo ""
echo "📈 KNOWLEDGE BASE STATS:"
echo "────────────────────────────────────────"
echo "  • Patterns: $(grep -c '^## Pattern:' "$MEMORY_DIR/knowledge/patterns.md" 2>/dev/null || echo 0)"
echo "  • Failures: $(grep -c '^## Error:\|^## Anti-Pattern:' "$MEMORY_DIR/knowledge/failures.md" 2>/dev/null || echo 0)"
echo "  • Decisions: $(grep -c '^## Decision:' "$MEMORY_DIR/knowledge/decisions.md" 2>/dev/null || echo 0)"
echo "  • Gotchas: $(grep -c '^## Gotcha:' "$MEMORY_DIR/knowledge/gotchas.md" 2>/dev/null || echo 0)"

echo ""
echo "════════════════════════════════════════════════════"
echo "  🚀 Ready to work. Knowledge loaded!"
echo "════════════════════════════════════════════════════"
echo ""

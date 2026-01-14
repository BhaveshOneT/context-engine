#!/bin/bash
# Daemon Learning Extraction Script
# Automatically extracts knowledge from active session when idle >5 min
# This simulates the Continuous-Claude daemon concept

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"
IDLE_THRESHOLD=300  # 5 minutes in seconds

echo "🤖 Daemon Learning Extractor Starting..."
echo "   Idle threshold: ${IDLE_THRESHOLD}s (5 minutes)"
echo ""

# Function to check if session is idle
check_idle() {
    local task_plan="$MEMORY_DIR/active/task_plan.md"

    if [ ! -f "$task_plan" ]; then
        return 1  # No active session
    fi

    # Check last modification time
    if [ "$(uname)" = "Darwin" ]; then
        local last_mod=$(stat -f "%m" "$task_plan")
    else
        local last_mod=$(stat -c "%Y" "$task_plan")
    fi

    local now=$(date +%s)
    local idle_time=$((now - last_mod))

    echo "   Session idle for: ${idle_time}s"

    if [ $idle_time -gt $IDLE_THRESHOLD ]; then
        return 0  # Is idle
    else
        return 1  # Not idle yet
    fi
}

# Function to extract patterns from context
extract_patterns() {
    local context_file="$MEMORY_DIR/active/context.md"
    local patterns_file="$MEMORY_DIR/knowledge/patterns.md"

    if [ ! -f "$context_file" ]; then
        return
    fi

    echo "   📚 Analyzing context for patterns..."

    # Look for sections marked for extraction
    if grep -q "Pattern:" "$context_file"; then
        echo "   ✓ Found pattern candidates"
        # In a full implementation, this would use AI to extract and format
        # For now, just flag it
        echo "   → Manual review recommended for: patterns.md"
    fi
}

# Function to extract failures
extract_failures() {
    local task_plan="$MEMORY_DIR/active/task_plan.md"
    local failures_file="$MEMORY_DIR/knowledge/failures.md"

    if [ ! -f "$task_plan" ]; then
        return
    fi

    echo "   ⚠️  Analyzing errors..."

    # Check error log table
    if grep -q "| .* | .* | Fixed |" "$task_plan"; then
        echo "   ✓ Found resolved errors"
        echo "   → These should be in failures.md"
    fi
}

# Function to extract decisions
extract_decisions() {
    local task_plan="$MEMORY_DIR/active/task_plan.md"
    local decisions_file="$MEMORY_DIR/knowledge/decisions.md"

    if [ ! -f "$task_plan" ]; then
        return
    fi

    echo "   🤔 Analyzing decisions..."

    # Check for decision section
    if grep -q "## Decisions Made This Session" "$task_plan"; then
        echo "   ✓ Found decision entries"
        echo "   → These should be in decisions.md"
    fi
}

# Function to update knowledge index
update_index() {
    local index_file="$MEMORY_DIR/knowledge/index.md"

    echo "   📇 Updating knowledge index..."

    # Count entries
    local pattern_count=$(grep -c "^## Pattern:" "$MEMORY_DIR/knowledge/patterns.md" 2>/dev/null || echo "0")
    local failure_count=$(grep -c "^## Error:\|^## Anti-Pattern:" "$MEMORY_DIR/knowledge/failures.md" 2>/dev/null || echo "0")
    local decision_count=$(grep -c "^## Decision:" "$MEMORY_DIR/knowledge/decisions.md" 2>/dev/null || echo "0")
    local gotcha_count=$(grep -c "^## Gotcha:" "$MEMORY_DIR/knowledge/gotchas.md" 2>/dev/null || echo "0")

    # Update statistics in index
    sed -i.bak "s/\*\*Patterns documented:\*\* .*/\*\*Patterns documented:** $pattern_count/" "$index_file"
    sed -i.bak "s/\*\*Failures prevented:\*\* .*/\*\*Failures prevented:** $failure_count/" "$index_file"
    sed -i.bak "s/\*\*Decisions recorded:\*\* .*/\*\*Decisions recorded:** $decision_count/" "$index_file"
    sed -i.bak "s/\*\*Gotchas tracked:\*\* .*/\*\*Gotchas tracked:** $gotcha_count/" "$index_file"

    local total=$((pattern_count + failure_count + decision_count + gotcha_count))
    sed -i.bak "s/\*\*Total knowledge entries:\*\* .*/\*\*Total knowledge entries:** $total/" "$index_file"

    rm "$index_file.bak" 2>/dev/null || true

    echo "   ✓ Index updated: $total total entries"
}

# Function to create YAML handoff
create_handoff() {
    local task_plan="$MEMORY_DIR/active/task_plan.md"
    local handoff_file="$MEMORY_DIR/handoffs/latest.yaml"

    if [ ! -f "$task_plan" ]; then
        return
    fi

    echo "   📦 Creating YAML handoff..."

    # Extract task name
    local task_name=$(grep "^# Task:" "$task_plan" | sed 's/# Task: //' | head -1)

    # Check if all phases complete
    local total_phases=$(grep -c "^- \[" "$task_plan" || echo "0")
    local complete_phases=$(grep -c "^- \[x\]" "$task_plan" || echo "0")

    local status="in_progress"
    if [ "$complete_phases" -eq "$total_phases" ] && [ "$total_phases" -gt 0 ]; then
        status="completed"
    fi

    # Create minimal YAML (full version would be more sophisticated)
    cat > "$handoff_file" << EOF
# Auto-generated handoff - $(date -u +"%Y-%m-%dT%H:%M:%SZ")
session_id: "sess_$(date +%Y%m%d)_auto"
task: "${task_name:-unknown_task}"
status: "$status"
generated_at: "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

phases_completed: $complete_phases
phases_total: $total_phases

next_session_hints: |
  Session was idle. Check active/task_plan.md for details.
  Knowledge extraction completed.

knowledge_updated: true
EOF

    echo "   ✓ Handoff created: $handoff_file"
}

# Main execution
main() {
    if check_idle; then
        echo ""
        echo "✓ Session idle >5 min. Starting extraction..."
        echo ""

        extract_patterns
        extract_failures
        extract_decisions
        update_index
        create_handoff

        echo ""
        echo "════════════════════════════════════════════════════"
        echo "  ✅ Learning extraction complete!"
        echo "════════════════════════════════════════════════════"
        echo ""
        echo "Next session will load this knowledge automatically."
        echo ""
    else
        echo "   Session not idle yet. Waiting..."
    fi
}

# Run main function
main "$@"

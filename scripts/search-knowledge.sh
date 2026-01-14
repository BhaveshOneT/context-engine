#!/bin/bash
# Search knowledge base for patterns, failures, decisions, gotchas
# Usage: ./search-knowledge.sh "search term"

set -e

MEMORY_DIR="${PROJECT_MEMORY_DIR:-.project-memory}"
SEARCH_TERM="${1:-}"

if [ -z "$SEARCH_TERM" ]; then
    echo "Usage: $0 \"search term\""
    echo ""
    echo "Examples:"
    echo "  $0 \"authentication\""
    echo "  $0 \"jwt token\""
    echo "  $0 \"database error\""
    exit 1
fi

echo "════════════════════════════════════════════════════"
echo "  🔍 Ultra-Planning V2: Knowledge Search"
echo "════════════════════════════════════════════════════"
echo ""
echo "Searching for: \"$SEARCH_TERM\""
echo ""

# Function to search a file and display results
search_file() {
    local file="$1"
    local filename=$(basename "$file")
    local matches=$(grep -i -n "$SEARCH_TERM" "$file" 2>/dev/null || echo "")

    if [ -n "$matches" ]; then
        echo "📄 $filename"
        echo "────────────────────────────────────────"
        echo "$matches" | while IFS=: read -r line_num content; do
            # Also show the section header
            local header=$(sed -n "1,${line_num}p" "$file" | grep "^##" | tail -1)
            echo "  Line $line_num: $header"
            echo "  $content"
            echo ""
        done
    fi
}

# Search patterns
if [ -f "$MEMORY_DIR/knowledge/patterns.md" ]; then
    search_file "$MEMORY_DIR/knowledge/patterns.md"
fi

# Search failures
if [ -f "$MEMORY_DIR/knowledge/failures.md" ]; then
    search_file "$MEMORY_DIR/knowledge/failures.md"
fi

# Search decisions
if [ -f "$MEMORY_DIR/knowledge/decisions.md" ]; then
    search_file "$MEMORY_DIR/knowledge/decisions.md"
fi

# Search gotchas
if [ -f "$MEMORY_DIR/knowledge/gotchas.md" ]; then
    search_file "$MEMORY_DIR/knowledge/gotchas.md"
fi

# Search index for quick links
if [ -f "$MEMORY_DIR/knowledge/index.md" ]; then
    echo "📇 Index Entries"
    echo "────────────────────────────────────────"
    grep -i "$SEARCH_TERM" "$MEMORY_DIR/knowledge/index.md" 2>/dev/null || echo "  No matches in index"
    echo ""
fi

# Search archive (most recent 5 tasks)
echo "📦 Recent Archives"
echo "────────────────────────────────────────"
if [ -d "$MEMORY_DIR/archive" ]; then
    find "$MEMORY_DIR/archive" -name "*.md" -type f | head -5 | while read -r archived_file; do
        local matches=$(grep -i -l "$SEARCH_TERM" "$archived_file" 2>/dev/null || echo "")
        if [ -n "$matches" ]; then
            echo "  Found in: $(dirname "$archived_file" | xargs basename)"
        fi
    done
else
    echo "  No archives yet"
fi

echo ""
echo "════════════════════════════════════════════════════"
echo "  Search complete"
echo "════════════════════════════════════════════════════"
echo ""

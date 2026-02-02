#!/bin/bash
# Ultra-Planning V3: Installation Script
# Install optional Python dependencies for advanced features

set -e

# Suppress LibreSSL warning from urllib3 when using macOS system Python
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore:urllib3 v2 only supports OpenSSL}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Ultra-Planning V3: Installing Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found!"
    echo "   Install Python3 first: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✓ Found: $PYTHON_VERSION"
echo ""

# Check if pip is available
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip not found!"
    echo "   Install pip for Python3 first"
    exit 1
fi

echo "✓ pip found"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing Python Packages"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Core dependencies
echo "1/3: Installing watchdog (File Watcher)..."
python3 -m pip install watchdog
echo "   ✓ watchdog installed"
echo ""

# Semantic search dependencies (optional but recommended)
echo "2/3: Installing sentence-transformers (Semantic Search)..."
echo "   (This may take a few minutes on first install)"
python3 -m pip install sentence-transformers numpy
echo "   ✓ sentence-transformers installed"
echo "   ✓ numpy installed"
echo ""

# Verify installations
echo "3/3: Verifying installations..."
python3 - <<'PY'
import importlib.metadata as md
import watchdog
version = getattr(watchdog, "__version__", None)
if not version:
    try:
        version = md.version("watchdog")
    except Exception:
        version = "unknown"
print("   ✓ watchdog version:", version)
PY
python3 - <<'PY'
import sentence_transformers
print("   ✓ sentence-transformers OK")
PY
python3 - <<'PY'
import numpy as np
print("   ✓ numpy version:", np.__version__)
PY
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 What's Enabled:"
echo "   • File Watcher (real-time monitoring)"
echo "   • Auto-Embedder (semantic search)"
echo "   • Knowledge Indexer (cross-references)"
echo "   • Template Injector (smart pre-fill)"
echo "   • Error Monitor (auto-capture)"
echo "   • Session Orchestrator (master controller)"
echo ""
echo "💡 Next Steps:"
echo ""
echo "1. Generate initial embeddings (optional, ~2 min):"
echo "   cd .project-memory"
echo "   python3 scripts/auto-embedder.py --embed"
echo ""
echo "2. Generate knowledge index:"
echo "   python3 scripts/knowledge-indexer.py"
echo ""
echo "3. Start your first V3 session:"
echo "   ./scripts/init-session.sh \"your-task-name\""
echo ""
echo "4. (Optional) Install git hooks for commit reminders:"
echo "   cp scripts/git-hooks/post-commit .git/hooks/post-commit"
echo "   chmod +x .git/hooks/post-commit"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Documentation:"
echo "   • README.md - Complete guide"
echo "   • QUICKSTART.md - 5-minute start"
echo "   • config.yaml - Customize behavior"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 Ultra-Planning V3 is ready! Happy coding!"
echo ""

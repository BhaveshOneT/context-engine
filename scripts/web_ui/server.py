#!/usr/bin/env python3
"""
Context Engine Web UI - Flask-based memory browser
Serves a simple interface for exploring sessions and knowledge.

Features:
- Browse session history
- View knowledge base entries by type
- Search with filters
- Prompt tracking and recording
- Session summaries
- Dark theme UI

Inspired by claude-mem's React viewer.
"""

import sys
import re
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Callable, Any

# Add scripts dir to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import config_loader
import cache_manager
import knowledge_parser
from observation_types import ObservationType, get_type_emoji

# Try to import Flask
try:
    from flask import Flask, render_template, jsonify, request, Response
except ImportError:
    print("Flask not installed. Install with: pip install flask")
    print("Then run: ./ce ui")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
MEMORY_DIR = SCRIPT_DIR.parent.parent
SESSIONS_DB = MEMORY_DIR / 'sessions.db'
HANDOFFS_DIR = MEMORY_DIR / 'handoffs'

# Flask app
app = Flask(__name__, template_folder='templates')


# ============================================================================
# Error Handling
# ============================================================================

class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@app.errorhandler(APIError)
def handle_api_error(error: APIError):
    """Handle custom API errors."""
    return jsonify({'error': error.message}), error.status_code


@app.errorhandler(Exception)
def handle_generic_error(error: Exception):
    """Handle unexpected errors."""
    logger.exception("Unexpected error: %s", error)
    return jsonify({'error': 'Internal server error'}), 500


def api_endpoint(f: Callable) -> Callable:
    """Decorator for API endpoints with error handling."""
    @wraps(f)
    def decorated(*args, **kwargs) -> Any:
        try:
            return f(*args, **kwargs)
        except APIError:
            raise  # Re-raise API errors to be handled by error handler
        except Exception as e:
            logger.exception("Error in %s: %s", f.__name__, e)
            return jsonify({'error': str(e)}), 500
    return decorated


# ============================================================================
# Input Validation
# ============================================================================

def validate_query(query: str, min_length: int = 2, max_length: int = 200) -> str:
    """
    Validate and sanitize search query.

    Args:
        query: Raw query string
        min_length: Minimum required length
        max_length: Maximum allowed length

    Returns:
        Sanitized query string

    Raises:
        APIError: If validation fails
    """
    if not query:
        raise APIError("Query is required", 400)

    query = query.strip()

    if len(query) < min_length:
        raise APIError(f"Query must be at least {min_length} characters", 400)

    if len(query) > max_length:
        query = query[:max_length]

    return query


def validate_type_filter(type_filter: str) -> str:
    """
    Validate observation type filter.

    Args:
        type_filter: Raw type filter string

    Returns:
        Validated type filter or 'all'
    """
    if not type_filter or type_filter == 'all':
        return 'all'

    valid_types = [t.value for t in ObservationType]
    if type_filter.lower() in valid_types:
        return type_filter.lower()

    return 'all'


def validate_prompt_text(text: str, max_length: int = 500) -> str:
    """
    Validate and sanitize prompt text.

    Args:
        text: Raw prompt text
        max_length: Maximum allowed length

    Returns:
        Sanitized prompt text

    Raises:
        APIError: If validation fails
    """
    if not text:
        raise APIError("Prompt text is required", 400)

    text = text.strip()

    if len(text) > max_length:
        text = text[:max_length]

    return text


# ============================================================================
# Routes - Main
# ============================================================================

@app.route('/')
def index():
    """Main dashboard."""
    return render_template('index.html')


# ============================================================================
# Routes - Knowledge Base
# ============================================================================

@app.route('/api/stats')
@api_endpoint
def get_stats():
    """Get knowledge base statistics."""
    stats = knowledge_parser.get_knowledge_stats()
    return jsonify(stats)


@app.route('/api/knowledge')
@api_endpoint
def get_knowledge():
    """Get all knowledge base entries with optional type filter."""
    type_filter = validate_type_filter(request.args.get('type', 'all'))

    entries = knowledge_parser.parse_all_knowledge_files(
        classify=True,
        type_filter=type_filter if type_filter != 'all' else None
    )

    return jsonify([entry.to_dict() for entry in entries])


@app.route('/api/search')
@api_endpoint
def search():
    """Search knowledge base by keyword."""
    query = request.args.get('q', '')
    type_filter = validate_type_filter(request.args.get('type', 'all'))

    if not query or len(query) < 2:
        return jsonify([])

    results = knowledge_parser.search_knowledge(
        query=query,
        type_filter=type_filter if type_filter != 'all' else None,
        max_results=20
    )

    return jsonify([entry.to_dict() for entry in results])


@app.route('/api/observation-types')
@api_endpoint
def get_observation_types():
    """Get list of observation types with counts."""
    type_counts = knowledge_parser.get_type_counts()

    types = [
        {
            'value': t.value,
            'label': t.value.title(),
            'emoji': get_type_emoji(t),
            'count': type_counts.get(t.value, 0)
        }
        for t in ObservationType
    ]

    return jsonify(types)


# ============================================================================
# Routes - Sessions
# ============================================================================

@app.route('/api/sessions')
@api_endpoint
def get_sessions():
    """Get session history from SQLite database."""
    if not SESSIONS_DB.exists():
        return jsonify([])

    conn = None
    try:
        conn = sqlite3.connect(str(SESSIONS_DB), timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, terminal, started_at, status
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 50
        """)
        sessions = [dict(row) for row in cursor.fetchall()]
        return jsonify(sessions)
    except sqlite3.Error as e:
        logger.error("Database error: %s", e)
        raise APIError(f"Database error: {e}", 500)
    finally:
        if conn:
            conn.close()


@app.route('/api/handoffs')
@api_endpoint
def get_handoffs():
    """Get recent handoffs."""
    handoffs = []

    if not HANDOFFS_DIR.exists():
        return jsonify([])

    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, handoffs unavailable")
        return jsonify([])

    for f in sorted(HANDOFFS_DIR.glob('*.yaml'), reverse=True)[:10]:
        if f.name.startswith('TEMPLATE'):
            continue

        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}

            handoffs.append({
                'filename': f.name,
                'task': data.get('task', 'Unknown'),
                'status': data.get('status', 'unknown'),
                'ended_at': data.get('ended_at', ''),
            })
        except Exception as e:
            logger.warning("Error reading handoff %s: %s", f.name, e)
            continue

    return jsonify(handoffs)


# ============================================================================
# Routes - Prompts
# ============================================================================

@app.route('/api/prompts')
@api_endpoint
def get_prompts():
    """Get current session prompts."""
    import prompt_tracker
    prompts = prompt_tracker.load_prompts_log()
    return jsonify(prompts)


@app.route('/api/prompts/record', methods=['POST'])
@api_endpoint
def record_prompt():
    """Record a new prompt."""
    import prompt_tracker

    data = request.get_json()
    if not data:
        raise APIError("Request body required", 400)

    prompt_text = validate_prompt_text(data.get('prompt', ''))
    entry = prompt_tracker.record_prompt(prompt_text)
    return jsonify(entry)


@app.route('/api/prompts/clear', methods=['POST'])
@api_endpoint
def clear_prompts():
    """Clear current session prompts."""
    import prompt_tracker
    prompt_tracker.clear_prompts_log()
    return jsonify({'status': 'cleared'})


# ============================================================================
# Routes - Summary
# ============================================================================

@app.route('/api/summary')
@api_endpoint
def get_summary():
    """Generate session summary."""
    import session_summarizer
    summary = session_summarizer.generate_structured_summary()
    return jsonify(summary)


# ============================================================================
# Health Check
# ============================================================================

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '2.0.0'
    })


# ============================================================================
# Cache Management
# ============================================================================

@app.route('/api/cache/clear', methods=['POST'])
@api_endpoint
def clear_cache():
    """Clear all caches (admin endpoint)."""
    cache_manager.clear_all_caches()
    return jsonify({'status': 'caches cleared'})


@app.route('/api/cache/stats')
@api_endpoint
def cache_stats():
    """Get cache statistics."""
    stats = cache_manager.get_all_cache_stats()

    # Convert CacheInfo objects to dicts
    formatted = {}
    for category, info_dict in stats.items():
        formatted[category] = {}
        for name, info in info_dict.items():
            formatted[category][name] = {
                'hits': info.hits,
                'misses': info.misses,
                'maxsize': info.maxsize,
                'currsize': info.currsize
            }

    return jsonify(formatted)


# ============================================================================
# Main
# ============================================================================

def main():
    """Start the web server."""
    port = config_loader.get('web_ui.port', 8765)
    debug = config_loader.get('web_ui.debug', False)

    print("=" * 60)
    print("  Context Engine Web UI")
    print("=" * 60)
    print()
    print(f"  Open in browser: http://localhost:{port}")
    print()
    print("  Endpoints:")
    print("    /api/stats           - Knowledge statistics")
    print("    /api/knowledge       - All knowledge entries")
    print("    /api/search?q=...    - Search knowledge")
    print("    /api/sessions        - Session history")
    print("    /api/prompts         - Prompt tracking")
    print("    /api/summary         - Session summary")
    print("    /api/health          - Health check")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()

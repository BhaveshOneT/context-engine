#!/usr/bin/env python3
"""
Context Engine: Prompt Tracker
Records user prompts with metadata for session continuity.

Features:
- Captures user requests when prompts are submitted
- Stores to active/.prompts_log.yaml
- Archives prompts when session ends
- Maintains prompt history across sessions

Inspired by claude-mem's UserPromptSubmit hook.
"""

import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader


# ============================================================================
# Constants
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
PROMPTS_LOG = ACTIVE_DIR / '.prompts_log.yaml'
PROMPTS_HISTORY = MEMORY_DIR / 'prompts_history.yaml'
SESSION_ID_FILE = ACTIVE_DIR / '.session_id'


# ============================================================================
# Prompt Recording
# ============================================================================

def get_current_session_id() -> str:
    """Get current session ID from active session file"""
    if SESSION_ID_FILE.exists():
        return SESSION_ID_FILE.read_text().strip()
    return f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def load_prompts_log() -> List[Dict]:
    """Load current session's prompts log"""
    if not PROMPTS_LOG.exists():
        return []
    try:
        with open(PROMPTS_LOG, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_prompts_log(prompts: List[Dict]):
    """Save prompts to log file"""
    PROMPTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMPTS_LOG, 'w', encoding='utf-8') as f:
        yaml.dump(prompts, f, default_flow_style=False, allow_unicode=True)


def record_prompt(
    prompt_text: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Record a user prompt with metadata.

    Args:
        prompt_text: The user's prompt text
        session_id: Optional session ID (auto-detected if not provided)
        metadata: Optional additional metadata

    Returns:
        The recorded prompt entry
    """
    max_length = config_loader.get('prompt_tracking.max_prompt_length', 500)

    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request': prompt_text[:max_length] if len(prompt_text) > max_length else prompt_text,
        'session_id': session_id or get_current_session_id(),
        'word_count': len(prompt_text.split()),
        'char_count': len(prompt_text)
    }

    if metadata:
        entry['metadata'] = metadata

    # Append to active prompts log
    prompts = load_prompts_log()
    prompts.append(entry)
    save_prompts_log(prompts)

    return entry


def get_first_prompt() -> Optional[str]:
    """
    Get the first prompt from the current session.
    Useful for extracting "what the user originally asked for".

    Returns:
        The first prompt text, or None if no prompts recorded
    """
    prompts = load_prompts_log()
    if prompts and len(prompts) > 0:
        return prompts[0].get('request', '')
    return None


def get_all_prompts() -> List[str]:
    """
    Get all prompts from the current session.

    Returns:
        List of prompt texts
    """
    prompts = load_prompts_log()
    return [p.get('request', '') for p in prompts]


def get_prompt_count() -> int:
    """Get number of prompts in current session"""
    return len(load_prompts_log())


# ============================================================================
# History Management
# ============================================================================

def load_prompts_history() -> List[Dict]:
    """Load prompts history across all sessions"""
    if not PROMPTS_HISTORY.exists():
        return []
    try:
        with open(PROMPTS_HISTORY, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_prompts_history(history: List[Dict]):
    """Save prompts history"""
    history_limit = config_loader.get('prompt_tracking.history_limit', 100)

    # Keep only the most recent prompts
    history = history[-history_limit:]

    with open(PROMPTS_HISTORY, 'w', encoding='utf-8') as f:
        yaml.dump(history, f, default_flow_style=False, allow_unicode=True)


def archive_prompts(session_id: str, archive_dir: Optional[Path] = None) -> int:
    """
    Archive current session's prompts.

    Args:
        session_id: The session ID being archived
        archive_dir: Optional archive directory to save prompts.yaml

    Returns:
        Number of prompts archived
    """
    prompts = load_prompts_log()
    if not prompts:
        return 0

    # Save to archive directory if provided
    if archive_dir:
        archive_dir = Path(archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / 'prompts.yaml'
        with open(archive_file, 'w', encoding='utf-8') as f:
            yaml.dump(prompts, f, default_flow_style=False)

    # Append to history
    history = load_prompts_history()
    history.extend(prompts)
    save_prompts_history(history)

    # Clear active log
    clear_prompts_log()

    return len(prompts)


def clear_prompts_log():
    """Clear the current session's prompts log"""
    if PROMPTS_LOG.exists():
        PROMPTS_LOG.unlink()


# ============================================================================
# Search & Query
# ============================================================================

def search_prompts(query: str, limit: int = 10) -> List[Dict]:
    """
    Search prompts in history by keyword.

    Args:
        query: Search query (case-insensitive)
        limit: Maximum results to return

    Returns:
        List of matching prompt entries
    """
    history = load_prompts_history()
    query_lower = query.lower()

    matches = [
        p for p in history
        if query_lower in p.get('request', '').lower()
    ]

    return matches[-limit:]  # Return most recent matches


def get_recent_prompts(limit: int = 10) -> List[Dict]:
    """
    Get most recent prompts from history.

    Args:
        limit: Maximum prompts to return

    Returns:
        List of recent prompt entries
    """
    history = load_prompts_history()
    return history[-limit:]


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI interface for prompt tracker"""
    parser = argparse.ArgumentParser(
        description='Context Engine Prompt Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s record "Add authentication to the API"
  %(prog)s list
  %(prog)s search "authentication"
  %(prog)s first
  %(prog)s count
  %(prog)s history
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record a new prompt')
    record_parser.add_argument('prompt', help='The prompt text to record')
    record_parser.add_argument('--session', help='Optional session ID')

    # List command
    subparsers.add_parser('list', help='List prompts in current session')

    # First command
    subparsers.add_parser('first', help='Get the first prompt (original request)')

    # Count command
    subparsers.add_parser('count', help='Get number of prompts in session')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search prompts in history')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')

    # History command
    history_parser = subparsers.add_parser('history', help='Show recent prompts from history')
    history_parser.add_argument('--limit', type=int, default=10, help='Max prompts')

    # Archive command
    archive_parser = subparsers.add_parser('archive', help='Archive current prompts')
    archive_parser.add_argument('--session', required=True, help='Session ID')
    archive_parser.add_argument('--dir', help='Archive directory')

    # Clear command
    subparsers.add_parser('clear', help='Clear current session prompts')

    args = parser.parse_args()

    if args.command == 'record':
        entry = record_prompt(args.prompt, session_id=args.session)
        print(f"Recorded prompt at {entry['timestamp']}")
        print(f"  Words: {entry['word_count']}, Chars: {entry['char_count']}")

    elif args.command == 'list':
        prompts = load_prompts_log()
        if not prompts:
            print("No prompts recorded in current session")
        else:
            print(f"Prompts in current session ({len(prompts)}):")
            print("-" * 50)
            for i, p in enumerate(prompts, 1):
                print(f"{i}. [{p['timestamp'][:19]}] {p['request'][:60]}...")

    elif args.command == 'first':
        first = get_first_prompt()
        if first:
            print(f"Original request: {first}")
        else:
            print("No prompts recorded")

    elif args.command == 'count':
        count = get_prompt_count()
        print(f"Prompts in session: {count}")

    elif args.command == 'search':
        results = search_prompts(args.query, args.limit)
        if not results:
            print(f"No prompts found matching '{args.query}'")
        else:
            print(f"Found {len(results)} prompts matching '{args.query}':")
            print("-" * 50)
            for p in results:
                print(f"[{p['timestamp'][:10]}] {p['request'][:70]}...")

    elif args.command == 'history':
        recent = get_recent_prompts(args.limit)
        if not recent:
            print("No prompts in history")
        else:
            print(f"Recent prompts ({len(recent)}):")
            print("-" * 50)
            for p in recent:
                session = p.get('session_id', 'unknown')[:20]
                print(f"[{p['timestamp'][:10]}] ({session}) {p['request'][:50]}...")

    elif args.command == 'archive':
        archive_path = Path(args.dir) if args.dir else None
        count = archive_prompts(args.session, archive_path)
        print(f"Archived {count} prompts for session {args.session}")

    elif args.command == 'clear':
        clear_prompts_log()
        print("Cleared current session prompts")

    else:
        # Default: show status
        prompts = load_prompts_log()
        history = load_prompts_history()
        print("Context Engine Prompt Tracker")
        print(f"  Current session: {get_prompt_count()} prompts")
        print(f"  History: {len(history)} prompts")
        print()
        print("Run with --help for usage information")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Session Registry - Cross-terminal awareness
SQLite database to track sessions across devices

Usage:
    python session-registry.py init                    # Initialize database
    python session-registry.py register <terminal>     # Register new session
    python session-registry.py list                    # List all sessions
    python session-registry.py latest                  # Get latest session
    python session-registry.py claim <file> <intent>   # Claim a file
"""

import sys
import os
import sqlite3
import argparse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = Path(os.environ.get("PROJECT_MEMORY_DIR", str(SCRIPT_DIR.parent)))
DB_PATH = MEMORY_DIR / "sessions.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        yield conn
    finally:
        conn.close()


def init_database(quiet: bool = False):
    """Initialize SQLite database with schema"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                terminal TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                last_handoff TEXT,
                knowledge_hash TEXT,
                status TEXT DEFAULT 'active'
            )
        """)

        # File claims table (distributed locking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_claims (
                file_path TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                claimed_at TIMESTAMP NOT NULL,
                intent TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # Handoffs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                yaml_path TEXT NOT NULL,
                task_name TEXT,
                status TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        conn.commit()

    if not quiet:
        print(f"Database initialized: {DB_PATH}")


def ensure_database():
    """Ensure database exists and schema is initialized"""
    init_database(quiet=True)


def _default_terminal() -> str:
    return os.environ.get("CE_TERMINAL") or os.environ.get("HOSTNAME") or "laptop"


def register_session(
    terminal: str = "laptop",
    session_id: str = None,
    started_at: str = None,
    status: str = "active",
    quiet: bool = False,
):
    """Register a new session"""
    ensure_database()

    if not terminal:
        terminal = _default_terminal()

    if session_id is None:
        session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{terminal}"

    now = started_at or datetime.now().isoformat()

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, terminal, started_at, status) VALUES (?, ?, ?, ?)",
            (session_id, terminal, now, status),
        )
        conn.execute(
            "UPDATE sessions SET terminal = ?, status = ? WHERE id = ?",
            (terminal, status, session_id),
        )
        conn.commit()

    if not quiet:
        print(f"Session registered: {session_id}")
        print(f"  Terminal: {terminal}")
        print(f"  Started: {now}")

    return session_id


def list_sessions():
    """List all sessions"""
    ensure_database()
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, terminal, started_at, status, last_handoff
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 20
        """)
        sessions = cursor.fetchall()

    if not sessions:
        print("No sessions found")
        return

    print("\nRecent Sessions:")
    print("-" * 80)
    print(f"{'Session ID':<35} {'Terminal':<12} {'Started':<20} {'Status':<10}")
    print("-" * 80)

    for session_id, terminal, started_at, status, _ in sessions:
        short_id = session_id[-25:] if len(session_id) > 25 else session_id
        print(f"{short_id:<35} {terminal:<12} {started_at[:19]:<20} {status:<10}")

    print("-" * 80)
    print(f"Total: {len(sessions)} sessions")


def get_latest_session():
    """Get the most recent session"""
    ensure_database()
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, terminal, started_at, last_handoff
            FROM sessions
            ORDER BY started_at DESC
            LIMIT 1
        """)
        session = cursor.fetchone()

    if not session:
        print("No sessions found")
        return

    session_id, terminal, started_at, handoff = session

    print("\nLatest Session:")
    print("-" * 60)
    print(f"  ID: {session_id}")
    print(f"  Terminal: {terminal}")
    print(f"  Started: {started_at}")
    if handoff:
        print(f"  Handoff: {handoff}")
    print("-" * 60)


def claim_file(filepath, intent, session_id=None):
    """Claim a file (distributed locking)"""
    ensure_database()
    # Get session ID if not provided
    if not session_id:
        with get_db_connection() as conn:
            result = conn.execute(
                "SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

        if not result:
            print("Error: No active session found. Register a session first.")
            return

        session_id = result[0]

    with get_db_connection() as conn:
        # Check if file is already claimed
        existing = conn.execute(
            "SELECT session_id FROM file_claims WHERE file_path = ?",
            (filepath,)
        ).fetchone()

        if existing:
            print(f"Warning: File already claimed by: {existing[0]}")
            print(f"   Intent: {intent}")
            return

        # Claim the file
        conn.execute(
            "INSERT INTO file_claims (file_path, session_id, claimed_at, intent) VALUES (?, ?, ?, ?)",
            (filepath, session_id, datetime.now().isoformat(), intent),
        )
        conn.commit()

    print(f"File claimed: {filepath}")
    print(f"  Session: {session_id}")
    print(f"  Intent: {intent}")


def end_session(
    session_id: str,
    status: str = "completed",
    handoff_path: str = None,
    ended_at: str = None,
    quiet: bool = False,
):
    """Mark a session as ended/completed"""
    if not session_id:
        if not quiet:
            print("Error: session_id required to end session")
        return

    ensure_database()
    now = ended_at or datetime.now().isoformat()

    with get_db_connection() as conn:
        # Ensure session exists
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, terminal, started_at, status) VALUES (?, ?, ?, ?)",
            (session_id, _default_terminal(), now, status),
        )
        conn.execute(
            "UPDATE sessions SET ended_at = ?, status = ?, last_handoff = ? WHERE id = ?",
            (now, status, handoff_path, session_id),
        )
        conn.commit()

    if not quiet:
        print(f"Session ended: {session_id}")
        print(f"  Status: {status}")
        print(f"  Ended: {now}")


def main():
    parser = argparse.ArgumentParser(description="Session Registry - Cross-terminal awareness")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument("--quiet", action="store_true", help="Suppress output")

    register_parser = subparsers.add_parser("register", help="Register new session")
    register_parser.add_argument("terminal", nargs="?", default=None, help="Terminal name (optional)")
    register_parser.add_argument("--id", dest="session_id", help="Session ID to register")
    register_parser.add_argument("--status", default="active", help="Session status")
    register_parser.add_argument("--started-at", dest="started_at", help="Override started timestamp")
    register_parser.add_argument("--quiet", action="store_true", help="Suppress output")

    list_parser = subparsers.add_parser("list", help="List sessions")

    latest_parser = subparsers.add_parser("latest", help="Show latest session")

    claim_parser = subparsers.add_parser("claim", help="Claim a file")
    claim_parser.add_argument("file_path", help="File path to claim")
    claim_parser.add_argument("intent", help="Intent for claim")
    claim_parser.add_argument("--session", dest="session_id", help="Session ID to associate")

    end_parser = subparsers.add_parser("end", help="End a session")
    end_parser.add_argument("--id", dest="session_id", required=True, help="Session ID to end")
    end_parser.add_argument("--status", default="completed", help="Final session status")
    end_parser.add_argument("--handoff", dest="handoff_path", help="Handoff YAML path")
    end_parser.add_argument("--ended-at", dest="ended_at", help="Override ended timestamp")
    end_parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    if args.command == "init":
        init_database(quiet=args.quiet)
    elif args.command == "register":
        terminal = args.terminal or _default_terminal()
        register_session(
            terminal=terminal,
            session_id=args.session_id,
            started_at=args.started_at,
            status=args.status,
            quiet=args.quiet,
        )
    elif args.command == "list":
        list_sessions()
    elif args.command == "latest":
        get_latest_session()
    elif args.command == "claim":
        claim_file(args.file_path, args.intent, session_id=args.session_id)
    elif args.command == "end":
        end_session(
            session_id=args.session_id,
            status=args.status,
            handoff_path=args.handoff_path,
            ended_at=args.ended_at,
            quiet=args.quiet,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

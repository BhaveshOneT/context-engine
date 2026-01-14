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
import json
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(os.environ.get("PROJECT_MEMORY_DIR", ".project-memory"))
DB_PATH = MEMORY_DIR / "sessions.db"


def init_database():
    """Initialize SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

    print(f"✓ Database initialized: {DB_PATH}")


def register_session(terminal="laptop"):
    """Register a new session"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{terminal}"
    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO sessions (id, terminal, started_at, status)
        VALUES (?, ?, ?, 'active')
    """,
        (session_id, terminal, now),
    )

    conn.commit()
    conn.close()

    print(f"✓ Session registered: {session_id}")
    print(f"  Terminal: {terminal}")
    print(f"  Started: {now}")

    return session_id


def list_sessions():
    """List all sessions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, terminal, started_at, status, last_handoff
        FROM sessions
        ORDER BY started_at DESC
        LIMIT 20
    """)

    sessions = cursor.fetchall()
    conn.close()

    if not sessions:
        print("No sessions found")
        return

    print("\n📋 Recent Sessions:")
    print("-" * 80)
    print(
        f"{'Session ID':<35} {'Terminal':<12} {'Started':<20} {'Status':<10}"
    )
    print("-" * 80)

    for session in sessions:
        session_id, terminal, started_at, status, handoff = session
        # Truncate session ID for display
        short_id = session_id[-25:] if len(session_id) > 25 else session_id
        print(
            f"{short_id:<35} {terminal:<12} {started_at[:19]:<20} {status:<10}"
        )

    print("-" * 80)
    print(f"Total: {len(sessions)} sessions")


def get_latest_session():
    """Get the most recent session"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, terminal, started_at, last_handoff
        FROM sessions
        ORDER BY started_at DESC
        LIMIT 1
    """)

    session = cursor.fetchone()
    conn.close()

    if not session:
        print("No sessions found")
        return

    session_id, terminal, started_at, handoff = session

    print("\n📌 Latest Session:")
    print("-" * 60)
    print(f"  ID: {session_id}")
    print(f"  Terminal: {terminal}")
    print(f"  Started: {started_at}")
    if handoff:
        print(f"  Handoff: {handoff}")
    print("-" * 60)


def claim_file(filepath, intent, session_id=None):
    """Claim a file (distributed locking)"""
    if not session_id:
        # Get latest session
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if not result:
            print("❌ No active session found. Register a session first.")
            return

        session_id = result[0]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if file is already claimed
    cursor.execute("SELECT session_id FROM file_claims WHERE file_path = ?", (filepath,))
    existing = cursor.fetchone()

    if existing:
        print(f"⚠️  File already claimed by: {existing[0]}")
        print(f"   Intent: {intent}")
        return

    # Claim the file
    now = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO file_claims (file_path, session_id, claimed_at, intent)
        VALUES (?, ?, ?, ?)
    """,
        (filepath, session_id, now, intent),
    )

    conn.commit()
    conn.close()

    print(f"✓ File claimed: {filepath}")
    print(f"  Session: {session_id}")
    print(f"  Intent: {intent}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} init                 # Initialize database")
        print(f"  {sys.argv[0]} register <terminal>  # Register new session")
        print(f"  {sys.argv[0]} list                 # List sessions")
        print(f"  {sys.argv[0]} latest               # Show latest session")
        print(f"  {sys.argv[0]} claim <file> <intent>  # Claim a file")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_database()
    elif command == "register":
        terminal = sys.argv[2] if len(sys.argv) > 2 else "laptop"
        register_session(terminal)
    elif command == "list":
        list_sessions()
    elif command == "latest":
        get_latest_session()
    elif command == "claim":
        if len(sys.argv) < 4:
            print("Usage: claim <file_path> <intent>")
            sys.exit(1)
        claim_file(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

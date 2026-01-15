#!/usr/bin/env python3
"""
Ultra-Planning V3: Session Orchestrator
Master controller coordinating all automation modules
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = MEMORY_DIR / 'scripts'
ACTIVE_DIR = MEMORY_DIR / 'active'
HANDOFFS_DIR = MEMORY_DIR / 'handoffs'


class SessionOrchestrator:
    """Coordinates all Ultra-Planning V3 automation"""

    def __init__(self):
        self.file_watcher_process: Optional[subprocess.Popen] = None
        self.task_name: Optional[str] = None

    def _inject_templates_task(self, task_name: str) -> Tuple[bool, str]:
        """Run template injection (for parallel execution)"""
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'template-injector.py'), task_name],
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return (True, result.stdout)
            else:
                return (False, "Template injection had issues (continuing anyway)")
        except Exception as e:
            return (False, f"Template injection failed: {e}")

    def _check_embeddings_task(self) -> Tuple[bool, str]:
        """Check embeddings status (for parallel execution)"""
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'auto-embedder.py'), '--status'],
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True,
                timeout=5
            )

            if 'Needs embedding' in result.stdout:
                return (False, "Embeddings need update (run auto-embedder.py --embed)")
            else:
                return (True, "Embeddings up to date")
        except:
            return (False, "Auto-embedder not available (install: pip install sentence-transformers numpy)")


    def start_session(self, task_name: str):
        """Start session with full automation"""
        self.task_name = task_name

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🚀 Ultra-Planning V3: Starting Session")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print(f"📝 Task: {task_name}")
        print()

        # Run Steps 1 & 2 in parallel (independent tasks)
        print("⚡ Running startup tasks in parallel...")
        print()

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            future_templates = executor.submit(self._inject_templates_task, task_name)
            future_embeddings = executor.submit(self._check_embeddings_task)

            # Wait for template injection (Step 1)
            print("📚 Step 1/4: Injecting past knowledge...")
            success, message = future_templates.result()
            if success:
                print(message)
            else:
                print(f"   ⚠️  {message}")

            # Wait for embeddings check (Step 2)
            print("🔮 Step 2/4: Checking semantic search readiness...")
            success, message = future_embeddings.result()
            if success:
                print(f"   ✓ {message}")
            else:
                print(f"   ⚠️  {message}")

        print()

        # 3. Start file watcher (background)
        print("👁️  Step 3/4: Starting file watcher...")
        try:
            self.file_watcher_process = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / 'file-watcher.py')],
                cwd=MEMORY_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Give it a moment to start
            time.sleep(1)

            if self.file_watcher_process.poll() is None:
                print("   ✓ File watcher started (monitoring in background)")
            else:
                print("   ⚠️  File watcher failed to start (install: pip install watchdog)")
                self.file_watcher_process = None
        except Exception as e:
            print(f"   ⚠️  File watcher not available: {e}")
            self.file_watcher_process = None

        print()

        # 4. Load previous session context (if exists)
        print("🔄 Step 4/4: Checking for previous session...")
        handoff_file = HANDOFFS_DIR / 'latest.yaml'

        if handoff_file.exists():
            print("   ✓ Previous session handoff found")
            print(f"     File: {handoff_file}")
            print("     (Review for context continuity)")
        else:
            print("   ℹ️  No previous session (fresh start)")

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Session ready! Automation active.")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("🎯 What's automated:")
        print("   • Template pre-filled with past knowledge")
        print("   • File watcher tracking progress in real-time")
        print("   • Error monitor available (pipe errors through it)")
        print("   • Smart extraction triggers on 2+ discoveries")
        print()
        print("💡 Tips:")
        print("   • Edit your plan: vim active/task_plan.md")
        print("   • Capture errors: npm test 2>&1 | scripts/error-monitor.py")
        print("   • Check extraction: scripts/smart-prompt-helper.py")
        print()
        print("Just code - the system handles the rest! 🚀")
        print()

    def on_idle(self):
        """Handle idle session - trigger extraction"""
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("⏰ Session idle detected, processing learnings...")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        # Check if extraction needed
        print("🧠 Checking if extraction needed...")
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'smart-prompt-helper.py'), '--check'],
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"   ⚠️  Extraction check failed: {e}")

        print()

        # Update knowledge index
        print("📇 Updating knowledge index...")
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'knowledge-indexer.py')],
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("   ✓ Index updated")
            else:
                print("   ⚠️  Index update had issues")
        except Exception as e:
            print(f"   ⚠️  Index update failed: {e}")

        print()

        # Check embeddings
        print("🔮 Checking vector embeddings...")
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'auto-embedder.py'), '--embed'],
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True,
                timeout=60
            )

            if 'up to date' in result.stdout.lower():
                print("   ✓ Embeddings current")
            elif 'Error' not in result.stdout:
                print("   ✓ Embeddings updated")
            else:
                print("   ℹ️  Embeddings not available (optional)")
        except:
            print("   ℹ️  Auto-embedder not available (optional)")

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Idle processing complete!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

    def end_session(self):
        """Clean shutdown with final extraction"""
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("👋 Ending session...")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        # Final extraction
        print("🧠 Final extraction pass...")
        self.on_idle()

        # Stop file watcher
        if self.file_watcher_process:
            print("🛑 Stopping file watcher...")
            try:
                self.file_watcher_process.terminate()
                self.file_watcher_process.wait(timeout=5)
                print("   ✓ File watcher stopped")
            except:
                self.file_watcher_process.kill()
                print("   ✓ File watcher stopped (forced)")

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Session ended. Knowledge preserved!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("💡 Next steps:")
        print("   • Review active/task_plan.md for completion")
        print("   • Run: scripts/archive-task.sh (when task complete)")
        print("   • Or continue next session with same context")
        print()

    def signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully"""
        print("\n\n⚠️  Interrupt received...")
        self.end_session()
        sys.exit(0)


def main():
    if len(sys.argv) < 2:
        print("Ultra-Planning V3: Session Orchestrator")
        print()
        print("Usage:")
        print("  session-orchestrator.py start <task-name>   # Start session")
        print("  session-orchestrator.py idle                # Process idle")
        print("  session-orchestrator.py end                 # End session")
        print()
        print("The orchestrator coordinates all automation modules.")
        print("Usually called automatically by init-session.sh and archive-task.sh")
        sys.exit(0)

    command = sys.argv[1]
    orchestrator = SessionOrchestrator()

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, orchestrator.signal_handler)
    signal.signal(signal.SIGTERM, orchestrator.signal_handler)

    if command == 'start':
        if len(sys.argv) < 3:
            print("Error: task name required")
            print("Usage: session-orchestrator.py start <task-name>")
            sys.exit(1)

        task_name = sys.argv[2]
        orchestrator.start_session(task_name)

    elif command == 'idle':
        orchestrator.on_idle()

    elif command == 'end':
        orchestrator.end_session()

    else:
        print(f"Unknown command: {command}")
        print("Use: start, idle, or end")
        sys.exit(1)


if __name__ == '__main__':
    main()

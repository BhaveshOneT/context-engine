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
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = MEMORY_DIR / 'scripts'
ACTIVE_DIR = MEMORY_DIR / 'active'
HANDOFFS_DIR = MEMORY_DIR / 'handoffs'
PID_DIR = MEMORY_DIR / '.pids'
LOG_DIR = MEMORY_DIR / '.logs'

# Add scripts dir to path for imports
sys.path.insert(0, str(SCRIPTS_DIR))
import config_loader


class SessionOrchestrator:
    """Coordinates all Ultra-Planning V3 automation"""

    def __init__(self):
        self.file_watcher_process: Optional[subprocess.Popen] = None
        self.task_name: Optional[str] = None

    def _run_script(self, script_name: str, args: list = None, timeout: int = None) -> Tuple[bool, str, int]:
        """Run a script and return (success, output/message, returncode)"""
        cmd = [sys.executable, str(SCRIPTS_DIR / script_name)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                cwd=MEMORY_DIR,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode == 0, result.stdout, result.returncode)
        except subprocess.TimeoutExpired:
            return (False, f"{script_name} timed out", 124)
        except Exception as e:
            return (False, f"{script_name} failed: {e}", 1)

    def _inject_templates_task(self, task_name: str) -> Tuple[bool, str]:
        """Run template injection (for parallel execution)"""
        success, output, _ = self._run_script('template-injector.py', [task_name])
        if success:
            return (True, output)
        return (False, "Template injection had issues (continuing anyway)")

    def _check_embeddings_task(self) -> Tuple[bool, str]:
        """Check embeddings status (for parallel execution)"""
        success, output, _ = self._run_script('auto-embedder.py', ['--status'], timeout=5)
        if not success:
            return (False, "Auto-embedder not available (install: pip install sentence-transformers numpy)")
        if 'Needs embedding' in output:
            return (False, "Embeddings need update (run auto-embedder.py --embed)")
        return (True, "Embeddings up to date")


    def start_session(self, task_name: str):
        """Start session with full automation"""
        self.task_name = task_name

        print("=" * 50)
        print("Starting Session")
        print("=" * 50)
        print()
        print(f"Task: {task_name}")
        print()

        # Run Steps 1 & 2 in parallel (independent tasks)
        print("Running startup tasks in parallel...")
        print()

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_templates = executor.submit(self._inject_templates_task, task_name)
            future_embeddings = executor.submit(self._check_embeddings_task)

            # Step 1: Template injection
            print("Step 1/4: Injecting past knowledge...")
            success, message = future_templates.result()
            print(message if success else f"   Warning: {message}")

            # Step 2: Embeddings check
            print("Step 2/4: Checking semantic search readiness...")
            success, message = future_embeddings.result()
            print(f"   {message}" if success else f"   Warning: {message}")

        print()

        # Step 3: Start file watcher (background)
        print("Step 3/4: Starting file watcher...")
        self._start_file_watcher()
        print()

        # Step 4: Check previous session
        print("Step 4/4: Checking for previous session...")
        handoff_file = HANDOFFS_DIR / 'latest.yaml'
        if handoff_file.exists():
            print(f"   Previous session handoff found: {handoff_file}")
        else:
            print("   No previous session (fresh start)")

        print()
        print("=" * 50)
        print("Session ready! Automation active.")
        print("=" * 50)
        print()
        print("What's automated:")
        print("   - Template pre-filled with past knowledge")
        print("   - File watcher tracking progress in real-time")
        print("   - Error monitor available (pipe errors through it)")
        print("   - Smart extraction triggers on 2+ discoveries")
        print()
        print("Tips:")
        print("   - Edit your plan: vim active/task_plan.md")
        print("   - Capture errors: npm test 2>&1 | scripts/error-monitor.py")
        print("   - Check extraction: scripts/smart-prompt-helper.py")
        print()

    def _start_file_watcher(self):
        """Start the file watcher background process"""
        if os.environ.get("CE_FILE_WATCHER_MANAGED") == "1":
            print("   File watcher managed by service manager (skipping)")
            return

        if config_loader.get('session.auto_start_watcher', True) is False:
            print("   File watcher disabled by config")
            return

        try:
            self.file_watcher_process = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / 'file-watcher.py')],
                cwd=MEMORY_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            time.sleep(1)

            if self.file_watcher_process.poll() is None:
                print("   File watcher started (monitoring in background)")
            else:
                print("   File watcher failed to start (install: pip install watchdog)")
                self.file_watcher_process = None
        except Exception as e:
            print(f"   File watcher not available: {e}")
            self.file_watcher_process = None

    def _read_pid(self, pid_file: Path) -> Optional[int]:
        if not pid_file.exists():
            return None
        try:
            return int(pid_file.read_text().strip())
        except Exception:
            return None

    def _pid_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _start_auto_embedder_async(self) -> bool:
        """Start auto-embedder in background (non-blocking)."""
        PID_DIR.mkdir(exist_ok=True)
        LOG_DIR.mkdir(exist_ok=True)
        pid_file = PID_DIR / 'auto_embedder.pid'

        existing_pid = self._read_pid(pid_file)
        if existing_pid and self._pid_running(existing_pid):
            print("   Auto-embedder already running")
            return False
        if existing_pid and not self._pid_running(existing_pid):
            pid_file.unlink(missing_ok=True)

        log_file = LOG_DIR / 'auto_embedder.log'
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / 'auto-embedder.py'), '--embed'],
                cwd=MEMORY_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

        pid_file.write_text(str(process.pid))
        print("   Auto-embedder started in background")
        return True

    def on_idle(self):
        """Handle idle session - trigger extraction"""
        print()
        print("=" * 50)
        print("Session idle detected, processing learnings...")
        print("=" * 50)
        print()

        # Check if extraction needed
        print("Checking if extraction needed...")
        success, output, _ = self._run_script('smart-prompt-helper.py', ['--check'])
        if success:
            print(output)
        else:
            print(f"   Warning: Extraction check failed")
        print()

        # Update knowledge index
        print("Updating knowledge index...")
        auto_index = config_loader.get('knowledge.auto_update_index', True)
        if auto_index:
            success, output, _ = self._run_script('knowledge-indexer.py', ['--if-changed'], timeout=30)
            if success:
                print(output.strip() or "   Done")
            else:
                print("   Index update had issues")
        else:
            print("   Skipped (auto_update_index disabled)")
        print()

        # Check embeddings
        print("Checking vector embeddings...")
        auto_embed = config_loader.get('knowledge.auto_generate_embeddings', True)
        if not auto_embed:
            print("   Skipped (auto_generate_embeddings disabled)")
        else:
            needs_update, output, code = self._run_script('auto-embedder.py', ['--needs-update'], timeout=10)
            if code == 0:
                print("   Embeddings current")
            elif code == 2:
                if config_loader.get('knowledge.embed_async', True):
                    self._start_auto_embedder_async()
                else:
                    print("   Embeddings need update, running auto-embedder...")
                    success, output, _ = self._run_script('auto-embedder.py', ['--embed'], timeout=120)
                    if success:
                        print("   Embeddings updated")
                    else:
                        print("   Auto-embedder not available (optional)")
            else:
                print("   Auto-embedder not available (optional)")

        print()
        print("=" * 50)
        print("Idle processing complete!")
        print("=" * 50)
        print()

    def end_session(self):
        """Clean shutdown with final extraction"""
        print()
        print("=" * 50)
        print("Ending session...")
        print("=" * 50)
        print()

        # Final extraction
        print("Final extraction pass...")
        self.on_idle()

        # Stop file watcher
        if self.file_watcher_process:
            print("Stopping file watcher...")
            try:
                self.file_watcher_process.terminate()
                self.file_watcher_process.wait(timeout=5)
                print("   File watcher stopped")
            except subprocess.TimeoutExpired:
                self.file_watcher_process.kill()
                print("   File watcher stopped (forced)")

        print()
        print("=" * 50)
        print("Session ended. Knowledge preserved!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("   - Review active/task_plan.md for completion")
        print("   - Run: scripts/archive-task.sh (when task complete)")
        print("   - Or continue next session with same context")
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

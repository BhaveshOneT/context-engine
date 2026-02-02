#!/usr/bin/env python3
"""
Context Engine: File Watcher
Real-time monitoring of file changes with intelligent reactions
"""

import sys
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import cache_manager
import config_loader

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: watchdog library not installed")
    print("   Install with: pip install watchdog")
    sys.exit(1)


# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
LEDGERS_DIR = MEMORY_DIR / 'ledgers'

# Debounce settings
try:
    DEBOUNCE_SECONDS = float(config_loader.get('monitoring.file_debounce_seconds', 2))
except (TypeError, ValueError):
    DEBOUNCE_SECONDS = 2.0


class SmartFileWatcher(FileSystemEventHandler):
    """Intelligent file watcher with automated reactions"""

    def __init__(self):
        self.last_update_times = {}  # file_path -> last_update_time

    def _should_process(self, file_path: Path) -> bool:
        """Check if enough time has passed since last update (debounce)"""
        current_time = time.time()
        last_time = self.last_update_times.get(str(file_path), 0)

        if current_time - last_time > DEBOUNCE_SECONDS:
            self.last_update_times[str(file_path)] = current_time
            return True
        return False

    def on_modified(self, event):
        """React to file modifications"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if not self._should_process(file_path):
            return

        # Clear file cache to get fresh content
        cache_manager.clear_file_cache()

        # Handle task_plan.md changes
        if file_path.name == 'task_plan.md' and file_path.parent == ACTIVE_DIR:
            self.handle_task_plan_update(file_path)

        # Handle context.md changes
        elif file_path.name == 'context.md' and file_path.parent == ACTIVE_DIR:
            self.handle_context_update(file_path)

        # Handle knowledge/ changes
        elif file_path.parent == KNOWLEDGE_DIR and file_path.suffix == '.md':
            self.handle_knowledge_update(file_path)

    def handle_task_plan_update(self, file_path: Path):
        """React to task_plan.md changes - update continuity ledger"""
        content = cache_manager.load_file_cached(str(file_path))
        if not content:
            return

        # Parse phases
        phases_match = re.search(r'## Phases\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
        if not phases_match:
            return

        phases_text = phases_match.group(1)

        # Count completed and total phases
        completed_count = len(re.findall(r'- \[x\]', phases_text, re.IGNORECASE))
        total_count = len(re.findall(r'- \[[ x]\]', phases_text))

        if total_count == 0:
            return

        # Get current phase (first uncompleted)
        uncompleted_match = re.search(r'- \[ \](.+)', phases_text)
        if uncompleted_match:
            current_phase = uncompleted_match.group(1).strip()
        elif completed_count > 0:
            current_phase = "All phases complete!"
        else:
            current_phase = None

        # Update continuity ledger
        self.update_continuity_ledger(completed_count, total_count, current_phase)
        print(f"Progress tracked: {completed_count}/{total_count} phases completed")

    def handle_context_update(self, file_path: Path):
        """React to context.md changes - check for extraction triggers"""
        content = cache_manager.load_file_cached(str(file_path))
        if not content:
            return

        # Count discoveries using multiple patterns
        discoveries = (
            len(re.findall(r'^\d+\.', content, re.MULTILINE)) +
            len(re.findall(r'^[-*]\s+.{20,}', content, re.MULTILINE)) +
            len(re.findall(r'(Discovered|Found|Learned):', content, re.IGNORECASE))
        )

        # Check if extraction should be triggered (2-action rule)
        if discoveries >= 2:
            print(f"2+ discoveries found ({discoveries}), ready for extraction")
            print("   Run: python3 scripts/smart-prompt-helper.py --create")

    def handle_knowledge_update(self, file_path: Path):
        """React to knowledge/ file changes"""
        print(f"Knowledge updated: {file_path.name}")
        print("   (Auto-embedder and indexer will process this)")

    def update_continuity_ledger(self, completed: int, total: int, current_phase: Optional[str]):
        """Update the continuity ledger with progress"""
        ledger_file = LEDGERS_DIR / 'CONTINUITY_active.md'

        if not ledger_file.exists():
            return

        content = cache_manager.load_file_cached(str(ledger_file))
        if not content:
            return

        # Update progress percentage
        progress_pct = int((completed / total) * 100) if total > 0 else 0

        # Update "Current Status" section
        status_pattern = r'(## Current Status\n\n)(.+?)(\n\n##|\Z)'
        status_replacement = f'''\\1**Progress:** {completed}/{total} phases ({progress_pct}%)
**Current Phase:** {current_phase if current_phase else "Starting..."}
**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\3'''

        content = re.sub(status_pattern, status_replacement, content, flags=re.DOTALL)

        # Update "What's Complete" section with checkmarks
        if completed > 0:
            complete_pattern = r'(## What\'s Complete\n\n)(.+?)(\n\n##|\Z)'
            completed_items = [f"- Phase {i+1}" for i in range(completed)]
            complete_replacement = f"\\1{chr(10).join(completed_items)}\\3"
            content = re.sub(complete_pattern, complete_replacement, content, flags=re.DOTALL)

        # Write back (clear cache first since we're writing)
        cache_manager.clear_file_cache()
        with open(ledger_file, 'w') as f:
            f.write(content)


def start_watching(watch_dirs: list = None):
    """Start the file watcher daemon"""
    if watch_dirs is None:
        watch_dirs = [ACTIVE_DIR, KNOWLEDGE_DIR]

    print("File Watcher: Starting...")
    print()
    print("Watching:")
    for watch_dir in watch_dirs:
        print(f"  - {watch_dir}")
    print()
    print("Monitoring:")
    print("  - active/task_plan.md -> Updates continuity ledger")
    print("  - active/context.md -> Checks extraction triggers")
    print("  - knowledge/*.md -> Flags for re-indexing/embedding")
    print()
    print("Press Ctrl+C to stop")
    print()

    event_handler = SmartFileWatcher()
    observer = Observer()

    for watch_dir in watch_dirs:
        if watch_dir.exists():
            observer.schedule(event_handler, str(watch_dir), recursive=False)

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nFile watcher stopped")
        observer.stop()

    observer.join()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Context Engine: File Watcher")
        print()
        print("Usage:")
        print("  file-watcher.py              # Start watching (default dirs)")
        print("  file-watcher.py --help       # Show this help")
        print()
        print("Monitors file changes and triggers automatic actions:")
        print("  • task_plan.md updates → continuity ledger updated")
        print("  • context.md changes → extraction readiness checked")
        print("  • knowledge/ changes → flagged for re-indexing")
        print()
        print("Requires: pip install watchdog")
        sys.exit(0)

    start_watching()


if __name__ == '__main__':
    main()

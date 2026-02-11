#!/usr/bin/env python3
"""
Ultra-Planning V3: File Watcher
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
import auto_extractor

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object


# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
LEDGERS_DIR = MEMORY_DIR / 'ledgers'

WATCHDOG_AVAILABLE = Observer is not None
DEBOUNCE_SECONDS = config_loader.get('monitoring.file_debounce_seconds', 2)


class SmartFileWatcher(FileSystemEventHandler):
    """Intelligent file watcher with automated reactions"""

    def __init__(self):
        self.last_update_times = {}  # file_path -> last_update_time
        self.last_discovery_count = 0
        self.last_decision_count = 0

    def _should_process(self, file_path: Path) -> bool:
        """Check if enough time has passed since last update (debounce)"""
        current_time = time.time()
        last_time = self.last_update_times.get(str(file_path), 0)

        if current_time - last_time > DEBOUNCE_SECONDS:
            self.last_update_times[str(file_path)] = current_time
            return True
        return False

    def process_modified_path(self, file_path: Path):
        """React to file modifications by path (used by both watchdog and polling)."""
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

    def on_modified(self, event):
        """React to watchdog file modifications"""
        if event.is_directory:
            return

        self.process_modified_path(Path(event.src_path))

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

        # Check decisions for auto extraction
        self.handle_decisions_update(content)

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

        min_discoveries = config_loader.get('auto_extraction.min_discoveries', 2)
        if discoveries < min_discoveries:
            return

        if discoveries <= self.last_discovery_count:
            return

        self.last_discovery_count = discoveries
        self.run_auto_extractor(reason=f"{discoveries} discoveries documented")

    def handle_knowledge_update(self, file_path: Path):
        """React to knowledge/ file changes"""
        print(f"Knowledge updated: {file_path.name}")
        print("   (Auto-embedder and indexer will process this)")

    def handle_decisions_update(self, content: str):
        decision_count = len(re.findall(r'-\s*\*\*Decision:\*\*\s*(.+)', content))
        if decision_count <= self.last_decision_count:
            return
        self.last_decision_count = decision_count
        self.run_auto_extractor(reason=f"{decision_count} decisions documented")

    def run_auto_extractor(self, reason: str):
        if not config_loader.get('auto_extraction.run_on_file_change', True):
            return

        print(f"Auto extraction triggered: {reason}")
        try:
            status = auto_extractor.extract(dry_run=False)
            counts = status.get('counts', {})
            summary = ", ".join([f"{k}:{v}" for k, v in counts.items()])
            print(f"Auto extraction complete ({summary})")
        except Exception as e:
            print(f"Auto extraction failed: {e}")

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


def _iter_watch_files(watch_dirs: list):
    """Yield markdown files from watch directories (non-recursive)."""
    for watch_dir in watch_dirs:
        if not watch_dir.exists():
            continue
        for file_path in watch_dir.glob('*.md'):
            if file_path.is_file():
                yield file_path


def _start_watchdog(event_handler: SmartFileWatcher, watch_dirs: list):
    """Start file watching via watchdog."""
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


def _start_polling(event_handler: SmartFileWatcher, watch_dirs: list, poll_seconds: float = 1.0):
    """Fallback watcher without external dependencies."""
    print("Mode: polling (watchdog not required)")

    mtimes = {}
    for file_path in _iter_watch_files(watch_dirs):
        try:
            mtimes[str(file_path)] = file_path.stat().st_mtime
        except OSError:
            continue

    try:
        while True:
            current_paths = set()
            for file_path in _iter_watch_files(watch_dirs):
                key = str(file_path)
                current_paths.add(key)
                try:
                    current_mtime = file_path.stat().st_mtime
                except OSError:
                    continue

                previous_mtime = mtimes.get(key)
                if previous_mtime is None:
                    mtimes[key] = current_mtime
                    continue

                if current_mtime > previous_mtime:
                    mtimes[key] = current_mtime
                    event_handler.process_modified_path(file_path)

            for stale_path in list(mtimes.keys()):
                if stale_path not in current_paths:
                    mtimes.pop(stale_path, None)

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\nFile watcher stopped")


def start_watching(watch_dirs: list = None, mode: str = 'auto') -> int:
    """Start the file watcher daemon."""
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
    print(f"Debounce: {DEBOUNCE_SECONDS}s")
    print("Press Ctrl+C to stop")
    print()

    event_handler = SmartFileWatcher()

    normalized_mode = mode.lower().strip()
    if normalized_mode not in {'auto', 'watchdog', 'polling'}:
        print(f"Error: invalid mode '{mode}' (expected auto, watchdog, or polling)")
        return 1

    if normalized_mode == 'watchdog' and not WATCHDOG_AVAILABLE:
        print("Warning: watchdog not installed, falling back to polling mode")
        normalized_mode = 'polling'

    if normalized_mode == 'watchdog' or (normalized_mode == 'auto' and WATCHDOG_AVAILABLE):
        print("Mode: watchdog")
        _start_watchdog(event_handler, watch_dirs)
        return 0

    _start_polling(event_handler, watch_dirs)
    return 0


def main():
    args = sys.argv[1:]

    if '--help' in args:
        print("Ultra-Planning V3: File Watcher")
        print()
        print("Usage:")
        print("  file-watcher.py                         # Start watching (auto mode)")
        print("  file-watcher.py --mode polling          # Force polling mode")
        print("  file-watcher.py --mode watchdog         # Force watchdog mode")
        print("  file-watcher.py --help       # Show this help")
        print()
        print("Monitors file changes and triggers automatic actions:")
        print("  • task_plan.md updates → continuity ledger updated")
        print("  • context.md changes → auto extraction (configurable)")
        print("  • knowledge/ changes → flagged for re-indexing")
        print()
        print("Modes:")
        print("  • auto (default): watchdog when available, else polling")
        print("  • watchdog: event-based (requires pip install watchdog)")
        print("  • polling: dependency-free fallback")
        sys.exit(0)

    mode = 'auto'
    if '--mode' in args:
        idx = args.index('--mode')
        if idx + 1 >= len(args):
            print("Error: --mode requires a value (auto, watchdog, polling)")
            sys.exit(1)
        mode = args[idx + 1]

    exit_code = start_watching(mode=mode)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

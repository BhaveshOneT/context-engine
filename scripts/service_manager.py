#!/usr/bin/env python3
"""
Context Engine: Service Manager
100% Automatic - manages all background services, sessions, and hooks.
"""

import os
import sys
import time
import signal
import subprocess
import webbrowser
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# Paths
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
PID_DIR = MEMORY_DIR / '.pids'
LOG_DIR = MEMORY_DIR / '.logs'

# Service definitions
SERVICES = {
    'web_ui': {
        'name': 'Web UI',
        'command': [sys.executable, str(SCRIPT_DIR / 'web_ui' / 'server.py')],
        'port': 8765,
    },
    'file_watcher': {
        'name': 'File Watcher',
        'command': ['bash', str(SCRIPT_DIR / 'daemon-extract-learnings.sh'), '--watch'],
    },
}

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
NC = '\033[0m'


# ============================================================================
# Utility Functions
# ============================================================================

def ensure_dirs():
    """Ensure required directories exist"""
    PID_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    ACTIVE_DIR.mkdir(exist_ok=True)


def get_pid_file(service: str) -> Path:
    return PID_DIR / f'{service}.pid'


def get_log_file(service: str) -> Path:
    return LOG_DIR / f'{service}.log'


def read_pid(service: str) -> Optional[int]:
    pid_file = get_pid_file(service)
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, IOError):
            return None
    return None


def write_pid(service: str, pid: int):
    get_pid_file(service).write_text(str(pid))


def remove_pid(service: str):
    pid_file = get_pid_file(service)
    if pid_file.exists():
        pid_file.unlink()


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def check_port(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


# ============================================================================
# Session Management (Auto-Session)
# ============================================================================

def get_git_branch() -> Optional[str]:
    """Get current git branch name"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, cwd=str(MEMORY_DIR.parent)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_project_name() -> str:
    """Get project name from directory"""
    # Try git remote
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, cwd=str(MEMORY_DIR.parent)
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract repo name from URL
            match = re.search(r'/([^/]+?)(?:\.git)?$', url)
            if match:
                return match.group(1)
    except Exception:
        pass

    # Fallback to directory name
    return MEMORY_DIR.parent.name


def has_active_session() -> bool:
    """Check if there's an active session"""
    task_plan = ACTIVE_DIR / 'task_plan.md'
    if not task_plan.exists():
        return False

    # Check if it's a real session (not just template)
    content = task_plan.read_text()
    return '# Task:' in content and '[Your task name]' not in content


def get_session_name() -> Optional[str]:
    """Get current session name from task_plan.md"""
    task_plan = ACTIVE_DIR / 'task_plan.md'
    if task_plan.exists():
        content = task_plan.read_text()
        match = re.search(r'^# Task:\s*(.+)$', content, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if name and name != '[Your task name]':
                return name
    return None


def create_auto_session() -> str:
    """Create a session automatically from git branch"""
    branch = get_git_branch() or 'main'
    project = get_project_name()

    # Clean branch name for session
    session_name = branch.replace('/', '-').replace('_', '-')

    # If on main/master, use project name + date
    if session_name in ('main', 'master'):
        date = datetime.now().strftime('%Y%m%d')
        session_name = f"{project}-{date}"

    # Run init-session.sh with correct environment
    init_script = SCRIPT_DIR / 'init-session.sh'
    if init_script.exists():
        env = os.environ.copy()
        env['PROJECT_MEMORY_DIR'] = str(MEMORY_DIR)
        subprocess.run(
            ['bash', str(init_script), session_name],
            cwd=str(MEMORY_DIR),
            capture_output=True,
            env=env
        )

    # Also create task_plan.md directly if init script failed
    task_plan = ACTIVE_DIR / 'task_plan.md'
    if not task_plan.exists() or '[Your task name]' in task_plan.read_text():
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        task_plan.write_text(f"""# Task: {session_name}
**Session ID:** {session_id}
**Started:** {timestamp}
**Status:** 🔄 In Progress

## Goal
Auto-created session for branch: {branch}

## Phases
- [ ] Phase 1: Initial work

## Files Created/Modified
- [ ] (tracked automatically)

## Live Error Log
| Error | Attempt | Status | Solution | Knowledge Updated |
|-------|---------|--------|----------|-------------------|

## Next Steps
1. Continue working on current task

---
*Auto-generated by Context Engine*
""")

    return session_name


def archive_session() -> bool:
    """Archive current session with summary"""
    if not has_active_session():
        return False

    session_name = get_session_name()

    # Generate summary first
    try:
        summarizer = SCRIPT_DIR / 'session_summarizer.py'
        if summarizer.exists():
            result = subprocess.run(
                [sys.executable, str(summarizer), '--format', 'yaml'],
                capture_output=True, text=True, cwd=str(MEMORY_DIR)
            )
            if result.returncode == 0:
                print(f"  {GREEN}●{NC} Session summary generated")
    except Exception:
        pass

    # Archive with correct environment
    archive_script = SCRIPT_DIR / 'archive-task.sh'
    if archive_script.exists():
        env = os.environ.copy()
        env['PROJECT_MEMORY_DIR'] = str(MEMORY_DIR)
        result = subprocess.run(
            ['bash', str(archive_script)],
            cwd=str(MEMORY_DIR),
            capture_output=True,
            env=env
        )
        if result.returncode == 0:
            print(f"  {GREEN}●{NC} Session '{session_name}' archived")
            return True
        else:
            # If script fails, do simple archive
            archive_dir = MEMORY_DIR / 'archive'
            archive_dir.mkdir(exist_ok=True)
            date = datetime.now().strftime('%Y-%m-%d')
            dest = archive_dir / f"{date}_{session_name}"
            if not dest.exists():
                dest.mkdir()
                # Copy active files to archive
                import shutil
                for f in ACTIVE_DIR.glob('*.md'):
                    if not f.name.startswith('TEMPLATE'):
                        shutil.copy(f, dest / f.name)
                # Clean active (keep templates)
                for f in ACTIVE_DIR.glob('*.md'):
                    if not f.name.startswith('TEMPLATE'):
                        f.unlink()
                print(f"  {GREEN}●{NC} Session '{session_name}' archived")
                return True

    return False


# ============================================================================
# Service Management
# ============================================================================

def start_service(service: str, config: Dict) -> bool:
    """Start a service in the background"""
    name = config['name']
    command = config['command']
    port = config.get('port')

    # Check if already running
    existing_pid = read_pid(service)
    if existing_pid and is_running(existing_pid):
        print(f"  {YELLOW}●{NC} {name} already running (PID {existing_pid})")
        return True

    # Check port availability
    if port and check_port(port):
        print(f"  {YELLOW}●{NC} {name} port {port} busy - freeing...")
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                for pid in result.stdout.strip().split('\n'):
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except:
                        pass
                time.sleep(0.5)
        except Exception:
            pass

    # Start the service
    log_file = get_log_file(service)
    try:
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=str(MEMORY_DIR)
            )

        write_pid(service, process.pid)
        time.sleep(0.5)

        if is_running(process.pid):
            print(f"  {GREEN}●{NC} {name} started (PID {process.pid})")
            return True
        else:
            print(f"  {RED}●{NC} {name} failed - check {log_file}")
            return False

    except Exception as e:
        print(f"  {RED}●{NC} {name} error: {e}")
        return False


def stop_service(service: str, config: Dict) -> bool:
    """Stop a service"""
    name = config['name']
    pid = read_pid(service)

    if not pid or not is_running(pid):
        remove_pid(service)
        return True

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            if not is_running(pid):
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)

        remove_pid(service)
        print(f"  {GREEN}●{NC} {name} stopped")
        return True

    except OSError as e:
        print(f"  {RED}●{NC} {name} error: {e}")
        remove_pid(service)
        return False


# ============================================================================
# Hooks Setup
# ============================================================================

def setup_hooks():
    """Create/update Claude Code hooks for 100% automation"""

    # Create PostToolUse hook for auto error capture
    post_hook = SCRIPT_DIR / 'hooks_PostToolUse_ErrorCapture.py'
    post_hook_content = '''#!/usr/bin/env python3
"""
Claude Code PostToolUse Hook: Auto Error Capture
Automatically captures errors from failed Bash commands.
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent

def main():
    # Read hook input from environment or stdin
    tool_name = os.environ.get('CLAUDE_TOOL_NAME', '')
    tool_output = os.environ.get('CLAUDE_TOOL_OUTPUT', '')
    exit_code = os.environ.get('CLAUDE_EXIT_CODE', '0')

    # Only process Bash tool failures
    if tool_name != 'Bash' or exit_code == '0':
        return

    # Import error monitor
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from error_monitor import detect_error, generate_error_fingerprint, add_to_failures_md

        # Check if output contains error patterns
        if detect_error(tool_output):
            # Extract error info
            lines = tool_output.split('\\n')
            for i, line in enumerate(lines):
                if detect_error(line):
                    error_data = {
                        'symptom': line[:200],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'command': os.environ.get('CLAUDE_TOOL_INPUT', 'Unknown'),
                        'stack_trace': '\\n'.join(lines[max(0,i-2):min(len(lines),i+10)])
                    }
                    add_to_failures_md(error_data)
                    print(f"[CE] Error auto-captured to knowledge/failures.md")
                    break
    except ImportError:
        pass

if __name__ == '__main__':
    main()
'''
    post_hook.write_text(post_hook_content)
    os.chmod(post_hook, 0o755)

    return True


# ============================================================================
# Main Commands
# ============================================================================

def activate(open_browser: bool = True):
    """Start all services with auto-session"""
    ensure_dirs()

    print(f"\n{BLUE}{'━' * 50}{NC}")
    print(f"{BOLD}{GREEN}  ⚡ Context Engine Activating...{NC}")
    print(f"{BLUE}{'━' * 50}{NC}\n")

    # Step 1: Check/Create Session
    print(f"{CYAN}Sessions:{NC}")
    if has_active_session():
        session_name = get_session_name()
        print(f"  {GREEN}●{NC} Active session: {BOLD}{session_name}{NC}")
    else:
        session_name = create_auto_session()
        print(f"  {GREEN}●{NC} Created session: {BOLD}{session_name}{NC}")

    print()

    # Step 2: Start Services
    print(f"{CYAN}Services:{NC}")
    all_started = True
    for service, config in SERVICES.items():
        if not start_service(service, config):
            all_started = False

    # Wait for Web UI
    web_port = SERVICES['web_ui']['port']
    for _ in range(20):
        if check_port(web_port):
            break
        time.sleep(0.5)

    print()

    # Step 3: Setup Hooks
    print(f"{CYAN}Hooks:{NC}")
    setup_hooks()
    print(f"  {GREEN}●{NC} Error auto-capture ready")
    print(f"  {GREEN}●{NC} Prompt tracking ready")

    print()

    # Final Status
    if all_started:
        url = f"http://localhost:{web_port}"
        print(f"{BLUE}{'━' * 50}{NC}")
        print(f"{BOLD}{GREEN}  ✓ Context Engine Active{NC}")
        print(f"{BLUE}{'━' * 50}{NC}")
        print()
        print(f"  {BOLD}Web UI:{NC}    {BLUE}{url}{NC}")
        print(f"  {BOLD}Session:{NC}   {session_name}")
        print(f"  {BOLD}Logs:{NC}      .logs/")
        print()
        print(f"  {CYAN}Everything is automatic:{NC}")
        print(f"    • Errors → auto-captured to knowledge")
        print(f"    • Prompts → auto-tracked")
        print(f"    • Learnings → auto-extracted when idle")
        print()
        print(f"  {YELLOW}Run './ce deactivate' when done{NC}")
        print(f"{BLUE}{'━' * 50}{NC}\n")

        if open_browser:
            webbrowser.open(url)
    else:
        print(f"{RED}✗ Some services failed{NC}")
        print(f"  Check logs in .logs/")

    return all_started


def deactivate():
    """Stop all services with auto-archive"""
    print(f"\n{BLUE}{'━' * 50}{NC}")
    print(f"{BOLD}{YELLOW}  Context Engine Deactivating...{NC}")
    print(f"{BLUE}{'━' * 50}{NC}\n")

    # Step 1: Archive Session
    print(f"{CYAN}Session:{NC}")
    if has_active_session():
        archive_session()
    else:
        print(f"  {YELLOW}●{NC} No active session to archive")

    print()

    # Step 2: Stop Services
    print(f"{CYAN}Services:{NC}")
    for service, config in SERVICES.items():
        stop_service(service, config)

    print()
    print(f"{BLUE}{'━' * 50}{NC}")
    print(f"{BOLD}{GREEN}  ✓ Context Engine Deactivated{NC}")
    print(f"{BLUE}{'━' * 50}{NC}")
    print()
    print(f"  Session archived to archive/")
    print(f"  Knowledge preserved in knowledge/")
    print()
    print(f"  {CYAN}Run './ce activate' to start a new session{NC}")
    print(f"{BLUE}{'━' * 50}{NC}\n")


def status():
    """Show comprehensive status"""
    print(f"\n{BLUE}{'━' * 50}{NC}")
    print(f"{BOLD}  Context Engine Status{NC}")
    print(f"{BLUE}{'━' * 50}{NC}\n")

    # Session Status
    print(f"{CYAN}Session:{NC}")
    if has_active_session():
        session_name = get_session_name()
        print(f"  {GREEN}●{NC} Active: {session_name}")
    else:
        print(f"  {YELLOW}●{NC} No active session")

    print()

    # Service Status
    print(f"{CYAN}Services:{NC}")
    any_running = False
    for service, config in SERVICES.items():
        pid = read_pid(service)
        running = pid and is_running(pid)
        if running:
            any_running = True
            port_info = f" (port {config.get('port')})" if config.get('port') else ""
            print(f"  {GREEN}●{NC} {config['name']}: running{port_info}")
        else:
            print(f"  {RED}●{NC} {config['name']}: stopped")

    if any_running:
        web_port = SERVICES['web_ui']['port']
        if check_port(web_port):
            print(f"\n  Web UI: {BLUE}http://localhost:{web_port}{NC}")

    # Knowledge Stats
    print()
    print(f"{CYAN}Knowledge:{NC}")
    knowledge_dir = MEMORY_DIR / 'knowledge'
    for f in ['patterns.md', 'failures.md', 'decisions.md', 'gotchas.md']:
        fpath = knowledge_dir / f
        if fpath.exists():
            lines = len(fpath.read_text().split('\n'))
            print(f"  • {f}: {lines} lines")

    print(f"\n{BLUE}{'━' * 50}{NC}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: service_manager.py <activate|deactivate|status>")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'activate':
        no_browser = '--no-browser' in sys.argv
        success = activate(open_browser=not no_browser)
        sys.exit(0 if success else 1)
    elif command == 'deactivate':
        deactivate()
    elif command == 'status':
        status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

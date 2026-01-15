#!/usr/bin/env python3
"""
Ultra-Planning V3: Error Monitor
Auto-capture errors from terminal output and document them
"""

import os
import sys
import re
import time
import select
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import subprocess


# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
ACTIVE_DIR = MEMORY_DIR / 'active'

# Error patterns to detect
ERROR_PATTERNS = [
    r'Error:|ERROR:|error:',
    r'Exception:|exception:',
    r'Failed:|FAILED:|failed:',
    r'Traceback \(most recent call last\)',
    r'npm ERR!',
    r'fatal:',
    r'✗|❌',
    r'SyntaxError:|TypeError:|ValueError:|AttributeError:',
    r'ModuleNotFoundError:|ImportError:',
    r'cannot find module|module not found',
    r'command not found',
    r'permission denied',
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ERROR_PATTERNS]


def detect_error(line: str) -> bool:
    """Check if line contains an error pattern"""
    return any(pattern.search(line) for pattern in COMPILED_PATTERNS)


def extract_error_symptom(lines: List[str], error_line_index: int) -> str:
    """Extract concise error symptom from error context"""
    error_line = lines[error_line_index].strip()

    # Try to extract the actual error message
    # Pattern 1: "Error: message"
    match = re.search(r'(?:Error|Exception|Failed):\s*(.+)', error_line, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 2: Just the error line itself (first 100 chars)
    return error_line[:100]


def extract_command_context(lines: List[str], error_line_index: int) -> Optional[str]:
    """Try to extract the command that caused the error"""
    # Look backwards for shell prompt indicators
    prompt_patterns = [
        r'^\$\s+(.+)$',  # $ command
        r'^>\s+(.+)$',  # > command
        r'^\w+@\w+.*\$\s+(.+)$',  # user@host$ command
    ]

    for i in range(error_line_index - 1, max(0, error_line_index - 10), -1):
        line = lines[i].strip()
        for pattern in prompt_patterns:
            match = re.match(pattern, line)
            if match:
                return match.group(1).strip()

    return None


def extract_stack_trace(lines: List[str], error_line_index: int) -> List[str]:
    """Extract stack trace or error context (up to 20 lines)"""
    # Include some lines before and many lines after the error
    start_idx = max(0, error_line_index - 2)
    end_idx = min(len(lines), error_line_index + 20)

    context = lines[start_idx:end_idx]

    # Stop at next shell prompt (new command)
    filtered_context = []
    for line in context:
        # Stop if we hit a new command prompt
        if re.match(r'^[\$>]\s+', line) and filtered_context:
            break
        filtered_context.append(line)

    return filtered_context


def generate_error_id(symptom: str) -> str:
    """Generate a short ID for the error (backward compatible)"""
    # Take first few words and make them a slug
    words = re.findall(r'\w+', symptom.lower())[:4]
    return '-'.join(words)


def generate_error_fingerprint(symptom: str, stack_trace: str = "") -> str:
    """
    Generate semantic fingerprint for error deduplication

    Normalizes error details to detect duplicates even with different:
    - Timestamps
    - File paths
    - Line numbers
    - Variable names

    Returns: 12-character hash for deduplication
    """
    import hashlib

    # Normalize symptom (remove variable parts)
    normalized = symptom.lower()

    # Remove timestamps (various formats)
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', normalized)
    normalized = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIME', normalized)
    normalized = re.sub(r'\d+ms', 'NUMms', normalized)

    # Remove file paths
    normalized = re.sub(r'/[^\s:]+/', '/PATH/', normalized)
    normalized = re.sub(r'[A-Z]:[^\s:]+', 'PATH', normalized)  # Windows paths

    # Remove line numbers
    normalized = re.sub(r':\d+:', ':LINE:', normalized)
    normalized = re.sub(r'line \d+', 'line NUM', normalized)

    # Remove memory addresses
    normalized = re.sub(r'0x[0-9a-fA-F]+', '0xADDR', normalized)

    # Extract stack trace signature (first 3 frames, normalized)
    stack_sig = ""
    if stack_trace:
        stack_lines = stack_trace.split('\n')[:3]  # First 3 frames
        for line in stack_lines:
            # Remove file paths and line numbers from stack
            normalized_line = re.sub(r'/[^\s:]+/', '', line)
            normalized_line = re.sub(r':\d+', '', normalized_line)
            stack_sig += normalized_line.strip()

    # Combine normalized symptom and stack signature
    combined = normalized + stack_sig

    # Generate MD5 hash and take first 12 characters
    fingerprint = hashlib.md5(combined.encode()).hexdigest()[:12]

    return fingerprint


def format_error_for_failures_md(error_data: Dict) -> str:
    """Format error for knowledge/failures.md"""
    return f"""
## Error: [Auto-Detected] {error_data['symptom']}
**Auto-Captured:** {error_data['timestamp']}
**Symptom:** {error_data['symptom']}
{f"**Command:** `{error_data['command']}`" if error_data['command'] else ""}
**Stack Trace:**
```
{error_data['stack_trace']}
```
**Status:** ⚠️ Needs solution (add solution once fixed)
**Solution:** (fill this in when you resolve the error)

---
"""


def add_to_failures_md(error_data: Dict) -> None:
    """Add error to knowledge/failures.md with fingerprint-based deduplication"""
    failures_file = KNOWLEDGE_DIR / 'failures.md'

    # Generate semantic fingerprint for deduplication
    fingerprint = generate_error_fingerprint(
        error_data['symptom'],
        error_data.get('stack_trace', '')
    )

    # Check if this exact error (by fingerprint) already exists
    if failures_file.exists():
        with open(failures_file, 'r') as f:
            content = f.read()

        # Check for fingerprint in ENTIRE file (not just last 5)
        if f'[fp:{fingerprint}]' in content:
            print(f"   (Duplicate error detected [fp:{fingerprint}], skipping)")
            return

    # Append to file with fingerprint metadata
    error_text = format_error_for_failures_md(error_data)

    # Add fingerprint to error metadata
    error_text = error_text.rstrip() + f"\n**Fingerprint:** `[fp:{fingerprint}]`\n\n---\n"

    with open(failures_file, 'a') as f:
        f.write(error_text)

    print(f"✅ Error auto-captured [fp:{fingerprint}] to knowledge/failures.md")


def add_to_error_log_table(error_data: Dict) -> None:
    """Add error to active/task_plan.md error log table"""
    task_plan_file = ACTIVE_DIR / 'task_plan.md'

    if not task_plan_file.exists():
        return

    with open(task_plan_file, 'r') as f:
        content = f.read()

    # Find the error log table
    table_pattern = r'(## Live Error Log.*?\| Error \| Attempt \| Status \| Solution \| Knowledge Updated \|\n\|[-|]+\|)(.*?)((?=\n##|\Z))'
    match = re.search(table_pattern, content, re.DOTALL)

    if not match:
        print(f"   (No error log table found in task_plan.md, skipping table update)")
        return

    # Extract existing rows
    before_table = match.group(1)
    existing_rows = match.group(2)
    after_table = match.group(3)

    # Count attempts for this error
    error_short = error_data['symptom'][:40]
    attempt_count = existing_rows.lower().count(error_short.lower()) + 1

    # Create new row
    new_row = f"\n| {error_short}... | {attempt_count} | 🔄 In Progress | (add solution here) | ⚠️ Pending |"

    # Insert new row at top of table (after header)
    updated_content = before_table + new_row + existing_rows + after_table

    # Replace in full content
    new_content = re.sub(table_pattern, lambda m: updated_content, content, flags=re.DOTALL)

    with open(task_plan_file, 'w') as f:
        f.write(new_content)

    print(f"✅ Error added to task_plan.md error log table")


def monitor_stdin():
    """Monitor stdin for errors (for pipe mode)"""
    print("🔥 Error Monitor: Watching for errors...")
    print("   (Monitoring terminal output - press Ctrl+C to stop)")
    print()

    buffer = []
    buffer_limit = 100  # Keep last 100 lines for context

    try:
        while True:
            # Check if stdin has data (non-blocking)
            if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                line = sys.stdin.readline()

                if not line:  # EOF
                    break

                # Print line (passthrough)
                print(line, end='')
                sys.stdout.flush()

                # Add to buffer
                buffer.append(line)
                if len(buffer) > buffer_limit:
                    buffer.pop(0)

                # Check for error
                if detect_error(line):
                    # Extract error details
                    error_line_index = len(buffer) - 1
                    symptom = extract_error_symptom(buffer, error_line_index)
                    command = extract_command_context(buffer, error_line_index)
                    stack_trace_lines = extract_stack_trace(buffer, error_line_index)
                    stack_trace = ''.join(stack_trace_lines)

                    error_data = {
                        'symptom': symptom,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'command': command,
                        'stack_trace': stack_trace,
                    }

                    # Document error
                    print()
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print("🔥 ERROR DETECTED:")
                    print(f"   {symptom}")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    add_to_failures_md(error_data)
                    add_to_error_log_table(error_data)
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print()

    except KeyboardInterrupt:
        print("\n🛑 Error monitor stopped")


def monitor_command(command: List[str]):
    """Run a command and monitor its output for errors"""
    print(f"🔥 Error Monitor: Running command with monitoring...")
    print(f"   Command: {' '.join(command)}")
    print()

    # Run command and capture output
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    buffer = []
    buffer_limit = 100

    for line in iter(process.stdout.readline, ''):
        if not line:
            break

        # Print line (passthrough)
        print(line, end='')
        sys.stdout.flush()

        # Add to buffer
        buffer.append(line)
        if len(buffer) > buffer_limit:
            buffer.pop(0)

        # Check for error
        if detect_error(line):
            error_line_index = len(buffer) - 1
            symptom = extract_error_symptom(buffer, error_line_index)
            command_str = ' '.join(command)
            stack_trace_lines = extract_stack_trace(buffer, error_line_index)
            stack_trace = ''.join(stack_trace_lines)

            error_data = {
                'symptom': symptom,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'command': command_str,
                'stack_trace': stack_trace,
            }

            # Document error
            print()
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("🔥 ERROR DETECTED:")
            print(f"   {symptom}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            add_to_failures_md(error_data)
            add_to_error_log_table(error_data)
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print()

    process.wait()
    return process.returncode


def main():
    if len(sys.argv) < 2:
        # Pipe mode: read from stdin
        monitor_stdin()
    elif sys.argv[1] == '--watch':
        # Pipe mode (explicit)
        monitor_stdin()
    elif sys.argv[1] == '--run':
        # Command mode: run command and monitor
        if len(sys.argv) < 3:
            print("Usage: error-monitor.py --run <command> [args...]")
            sys.exit(1)
        command = sys.argv[2:]
        exit_code = monitor_command(command)
        sys.exit(exit_code)
    else:
        print("Ultra-Planning V3: Error Monitor")
        print()
        print("Usage:")
        print("  error-monitor.py --watch          # Monitor stdin (pipe mode)")
        print("  error-monitor.py --run <cmd>      # Run command with monitoring")
        print()
        print("Examples:")
        print("  npm test 2>&1 | error-monitor.py")
        print("  error-monitor.py --run npm test")
        sys.exit(1)


if __name__ == '__main__':
    main()

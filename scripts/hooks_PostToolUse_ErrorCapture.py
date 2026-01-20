#!/usr/bin/env python3
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
            lines = tool_output.split('\n')
            for i, line in enumerate(lines):
                if detect_error(line):
                    error_data = {
                        'symptom': line[:200],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'command': os.environ.get('CLAUDE_TOOL_INPUT', 'Unknown'),
                        'stack_trace': '\n'.join(lines[max(0,i-2):min(len(lines),i+10)])
                    }
                    add_to_failures_md(error_data)
                    print(f"[CE] Error auto-captured to knowledge/failures.md")
                    break
    except ImportError:
        pass

if __name__ == '__main__':
    main()

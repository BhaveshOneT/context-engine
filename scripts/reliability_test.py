#!/usr/bin/env python3
"""
Context Engine reliability integration test:
- durable WAL append
- replay after simulated crash
- idempotent re-apply (no duplicate prompt/error rows)
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).parent
EVENT_STORE = SCRIPT_DIR / 'event_store.py'
PYTHON = os.environ.get('PYTHON', 'python3')


TASK_PLAN_FIXTURE = """# Task: reliability-test
**Session ID:** sess_test
**Started:** 2026-02-11 00:00:00
**Status:** in_progress

## Goal
Verify event replay reliability.

## Live Error Log
| Error | Attempt | Status | Solution | Knowledge Updated |
|-------|---------|--------|----------|-------------------|

## Next Steps
1. Finish test
"""


def run(cmd, env):
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}):\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def count_occurrences(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return len(re.findall(pattern, path.read_text(encoding='utf-8'), flags=re.MULTILINE))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='ce-reliability-') as tmp:
        root = Path(tmp)
        active = root / 'active'
        knowledge = root / 'knowledge'
        active.mkdir(parents=True, exist_ok=True)
        knowledge.mkdir(parents=True, exist_ok=True)

        (active / 'task_plan.md').write_text(TASK_PLAN_FIXTURE, encoding='utf-8')
        (active / '.session_id').write_text('sess_test', encoding='utf-8')
        (knowledge / 'failures.md').write_text('# Failures\n', encoding='utf-8')

        env = os.environ.copy()
        env['PROJECT_MEMORY_DIR'] = str(root)

        prompt_out = run(
            [PYTHON, str(EVENT_STORE), 'record-prompt', 'implement jwt token rotation', '--session', 'sess_test'],
            env,
        )
        prompt_event_id = prompt_out.split(':')[-1].strip()

        error_out = run(
            [
                PYTHON, str(EVENT_STORE), 'record-error',
                '--symptom', 'TypeError: cannot read token',
                '--cmd', 'npm test',
                '--stack', 'at auth.ts:42',
                '--session', 'sess_test',
            ],
            env,
        )
        error_event_id = error_out.split(':')[-1].strip()

        prompts_log = active / '.prompts_log.yaml'
        task_plan = active / 'task_plan.md'
        failures = knowledge / 'failures.md'

        prompts = yaml.safe_load(prompts_log.read_text(encoding='utf-8')) or []
        assert sum(1 for p in prompts if p.get('event_id') == prompt_event_id) == 1
        assert count_occurrences(task_plan, re.escape(f"[ev:{error_event_id}]")) == 1
        assert count_occurrences(
            failures,
            r'^## Error: \[Auto-Detected\] TypeError: cannot read token$',
        ) == 1

        # Simulate crash before checkpoint persisted: rewind offset to 0 and replay everything.
        (active / '.events_state.json').write_text(
            json.dumps({'last_applied_offset': 0}, indent=2),
            encoding='utf-8',
        )

        run([PYTHON, str(EVENT_STORE), 'replay'], env)

        prompts = yaml.safe_load(prompts_log.read_text(encoding='utf-8')) or []
        assert sum(1 for p in prompts if p.get('event_id') == prompt_event_id) == 1
        assert count_occurrences(task_plan, re.escape(f"[ev:{error_event_id}]")) == 1
        assert count_occurrences(
            failures,
            r'^## Error: \[Auto-Detected\] TypeError: cannot read token$',
        ) == 1

    print('PASS: durable replay is idempotent for prompt/error events')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Context Engine: Durable event store (WAL + replay).

This module provides:
- append-only JSONL event log for critical captures
- replay from last applied byte offset
- idempotent apply handlers for prompt/error events
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = Path(os.environ.get('PROJECT_MEMORY_DIR', SCRIPT_DIR.parent))
ACTIVE_DIR = MEMORY_DIR / 'active'
EVENTS_LOG = ACTIVE_DIR / '.events.jsonl'
EVENTS_STATE = ACTIVE_DIR / '.events_state.json'
PROMPTS_LOG = ACTIVE_DIR / '.prompts_log.yaml'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _ensure_active_dir() -> None:
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)


def _fsync_parent(path: Path) -> None:
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_json_atomic(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    _fsync_parent(path)


def _read_state() -> Dict:
    if not EVENTS_STATE.exists():
        return {'last_applied_offset': 0, 'updated_at': _utc_now()}
    try:
        with EVENTS_STATE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {'last_applied_offset': 0, 'updated_at': _utc_now()}


def _write_state(offset: int) -> None:
    state = {
        'last_applied_offset': max(0, int(offset)),
        'updated_at': _utc_now(),
    }
    _write_json_atomic(EVENTS_STATE, state)


def _load_prompts() -> List[Dict]:
    if not PROMPTS_LOG.exists():
        return []
    try:
        with PROMPTS_LOG.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_prompts(prompts: List[Dict]) -> None:
    PROMPTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROMPTS_LOG.with_suffix(PROMPTS_LOG.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        yaml.dump(prompts, f, default_flow_style=False, allow_unicode=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PROMPTS_LOG)
    _fsync_parent(PROMPTS_LOG)


def append_event(event_type: str, payload: Dict, session_id: str = '') -> Dict:
    """Append a single event to the durable JSONL log."""
    _ensure_active_dir()
    event = {
        'id': uuid.uuid4().hex,
        'timestamp': _utc_now(),
        'type': event_type,
        'session_id': session_id or '',
        'payload': payload or {},
        'schema_version': 1,
    }

    line = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    with EVENTS_LOG.open('ab') as f:
        f.seek(0, os.SEEK_END)
        start = f.tell()
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
        end = f.tell()

    _fsync_parent(EVENTS_LOG)
    event['_start'] = start
    event['_end'] = end
    return event


def _read_events_from_offset(offset: int) -> Tuple[List[Dict], int]:
    if not EVENTS_LOG.exists():
        return [], offset

    events: List[Dict] = []
    with EVENTS_LOG.open('rb') as f:
        f.seek(max(0, int(offset)))
        while True:
            line_start = f.tell()
            raw = f.readline()
            if not raw:
                return events, f.tell()

            line_end = f.tell()
            text = raw.decode('utf-8', errors='replace').strip()
            if not text:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                # Most likely a partial/truncated tail write. Retry later.
                return events, line_start

            if not isinstance(event, dict):
                continue

            event['_start'] = line_start
            event['_end'] = line_end
            events.append(event)


def _apply_prompt_recorded(event: Dict) -> bool:
    event_id = event.get('id', '')
    payload = event.get('payload', {}) or {}
    entry = payload.get('entry')
    if not isinstance(entry, dict):
        return False

    prompts = _load_prompts()
    if any(p.get('event_id') == event_id for p in prompts):
        return True

    durable_entry = dict(entry)
    durable_entry['event_id'] = event_id
    prompts.append(durable_entry)
    _save_prompts(prompts)
    return True


def _apply_error_captured(event: Dict) -> bool:
    payload = event.get('payload', {}) or {}
    error_data = payload.get('error_data')
    if not isinstance(error_data, dict):
        return False

    sys.path.insert(0, str(SCRIPT_DIR))
    from error_monitor import add_to_failures_md, add_to_error_log_table

    event_id = event.get('id', '')
    add_to_failures_md(error_data)
    add_to_error_log_table(error_data, event_id=event_id)
    return True


def apply_event(event: Dict) -> bool:
    event_type = event.get('type', '')
    if event_type == 'prompt.recorded':
        return _apply_prompt_recorded(event)
    if event_type == 'error.captured':
        return _apply_error_captured(event)

    # Unknown events are treated as no-op but considered applied.
    return True


def record_prompt_event(entry: Dict, session_id: str = '') -> Dict:
    event = append_event('prompt.recorded', {'entry': entry}, session_id=session_id)
    if apply_event(event):
        _write_state(event['_end'])
    return event


def record_error_event(error_data: Dict, session_id: str = '') -> Dict:
    event = append_event('error.captured', {'error_data': error_data}, session_id=session_id)
    if apply_event(event):
        _write_state(event['_end'])
    return event


def replay_pending_events() -> Dict:
    state = _read_state()
    offset = int(state.get('last_applied_offset', 0))

    events, _ = _read_events_from_offset(offset)
    applied = 0
    failed = 0
    last_good_offset = offset

    for event in events:
        try:
            ok = apply_event(event)
        except Exception:
            ok = False

        if not ok:
            failed += 1
            break

        applied += 1
        last_good_offset = int(event.get('_end', last_good_offset))
        _write_state(last_good_offset)

    return {
        'from_offset': offset,
        'to_offset': last_good_offset,
        'applied': applied,
        'failed': failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Context Engine durable event store')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('replay', help='Replay pending events from the durable log')

    p_record_prompt = sub.add_parser('record-prompt', help='Append + apply prompt event')
    p_record_prompt.add_argument('prompt', help='Prompt text')
    p_record_prompt.add_argument('--session', default='', help='Session ID')

    p_record_error = sub.add_parser('record-error', help='Append + apply error event')
    p_record_error.add_argument('--symptom', required=True, help='Error symptom text')
    p_record_error.add_argument('--cmd', default='', help='Failing command')
    p_record_error.add_argument('--stack', default='', help='Stack/context text')
    p_record_error.add_argument('--session', default='', help='Session ID')

    args = parser.parse_args()

    if args.command == 'replay':
        status = replay_pending_events()
        print(
            f"Replay complete: applied={status['applied']} "
            f"failed={status['failed']} offset={status['from_offset']}->{status['to_offset']}"
        )
        return 0 if status['failed'] == 0 else 1

    if args.command == 'record-prompt':
        entry = {
            'timestamp': _utc_now(),
            'request': args.prompt,
            'session_id': args.session,
            'word_count': len(args.prompt.split()),
            'char_count': len(args.prompt),
        }
        event = record_prompt_event(entry, session_id=args.session)
        print(f"Recorded prompt event: {event['id']}")
        return 0

    if args.command == 'record-error':
        error_data = {
            'symptom': args.symptom,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'command': args.cmd,
            'stack_trace': args.stack,
        }
        event = record_error_event(error_data, session_id=args.session)
        print(f"Recorded error event: {event['id']}")
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())

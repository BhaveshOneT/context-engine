#!/usr/bin/env python3
"""
Context Engine: Auto Extractor
Automatically extracts patterns, decisions, gotchas, and failures from
active/context.md and active/task_plan.md into knowledge/*.md
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import config_loader

MEMORY_DIR = SCRIPT_DIR.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
STATUS_FILE = ACTIVE_DIR / '.extraction_status.json'


@dataclass
class ExtractItem:
    kind: Optional[str]
    title: str
    source: str
    details: Dict[str, str]
    raw_text: str


_FAILURE_KEYWORDS = ('error', 'exception', 'failed', 'traceback', 'crash')
_GOTCHA_KEYWORDS = ('surprising', 'unexpected', 'gotcha', 'quirk')
_DECISION_KEYWORDS = ('decided', 'chose', 'switch', 'migrate')
_PLACEHOLDER_VALUES = {
    'tbd', 'todo', 'n/a', 'na', 'unknown', '(fill this in)', '(add solution here)',
}
_GENERIC_PHRASES = (
    'improve performance',
    'fix bug',
    'update code',
    'refactor code',
    'clean up',
    'make it better',
    'handle edge cases',
    'add tests',
    'investigate issue',
)
_TECHNICAL_SIGNAL_PATTERNS = (
    r'`[^`]+`',
    r'\b[a-zA-Z0-9_/.-]+\.(ts|tsx|js|jsx|py|go|rs|java|json|yaml|yml|sql|md)\b',
    r'\b(jwt|oauth|api|http|grpc|redis|cache|postgres|mysql|sqlite|index|migration|schema|ci|lint|build|hook)\b',
    r'(::|=>|==|!=|\(|\)|/|_)',
)


def _load(path: Path) -> str:
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8')


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def _fingerprint(kind: str, title: str) -> str:
    payload = f"{kind}:{title.strip().lower()}"
    return hashlib.md5(payload.encode('utf-8')).hexdigest()[:12]


def _already_present(path: Path, fp: str) -> bool:
    if not path.exists():
        return False
    return f"[auto:{fp}]" in path.read_text(encoding='utf-8')


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\n(.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ''


def _is_placeholder(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip()
    if stripped.startswith('[') and stripped.endswith(']'):
        return True
    lowered = stripped.lower()
    if lowered in _PLACEHOLDER_VALUES:
        return True
    placeholders = {
        '[brief description]': True,
        '[error encountered]': True,
        '[choice made]': True,
        '[surprising behavior]': True,
        '[title]': True,
        '[what was chosen]': True,
    }
    return placeholders.get(lowered, False)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _is_generic_text(text: str) -> bool:
    lowered = _normalize_whitespace(text).lower()
    if not lowered:
        return True
    if any(phrase in lowered for phrase in _GENERIC_PHRASES):
        return True
    if len(lowered.split()) < 3:
        return True
    return False


def _has_technical_signal(text: str) -> bool:
    haystack = text or ''
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in _TECHNICAL_SIGNAL_PATTERNS)


def _clean_detail_value(value: str) -> str:
    cleaned = _normalize_whitespace(value)
    if _is_placeholder(cleaned):
        return ''
    return cleaned


def _sanitize_item(item: ExtractItem) -> Optional[ExtractItem]:
    title = _normalize_whitespace(item.title)
    raw_text = _normalize_whitespace(item.raw_text)
    details = {k: _clean_detail_value(v) for k, v in item.details.items() if _clean_detail_value(v)}

    if _is_placeholder(title) or len(title) < 8:
        return None

    return ExtractItem(
        kind=item.kind,
        title=title,
        source=item.source,
        details=details,
        raw_text=raw_text or title,
    )


def _item_quality(item: ExtractItem, kind: str) -> float:
    score = 0.0
    text_blob = " ".join([item.title, item.raw_text] + list(item.details.values()))
    lowered = text_blob.lower()

    if 12 <= len(item.title) <= 140:
        score += 0.2
    if _has_technical_signal(text_blob):
        score += 0.35
    if item.details:
        score += 0.2
    if not _is_generic_text(item.title):
        score += 0.15
    if 'active/task_plan.md (decisions)' in item.source:
        score += 0.1

    if kind == 'decision':
        if item.details.get('why'):
            score += 0.2
        else:
            score -= 0.2

    if kind == 'failure':
        if re.search(r'(because|due to|root cause|when)', lowered):
            score += 0.2
        else:
            score -= 0.15

    if kind == 'pattern':
        if item.details.get('found') or item.details.get('relevance'):
            score += 0.15

    if _is_generic_text(text_blob):
        score -= 0.35
    if 'tbd' in lowered or 'todo' in lowered:
        score -= 0.2

    return max(0.0, min(1.0, score))


def _classify_kind(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in _FAILURE_KEYWORDS):
        return 'failure'
    if any(k in lowered for k in _GOTCHA_KEYWORDS):
        return 'gotcha'
    if any(k in lowered for k in _DECISION_KEYWORDS):
        return 'decision'
    return 'pattern'


def _parse_extractable_context(content: str) -> Tuple[List[ExtractItem], Optional[str]]:
    section = _extract_section(content, 'Extractable Knowledge')
    if not section:
        return [], None

    items: List[ExtractItem] = []
    lines = section.splitlines()
    updated_lines = list(lines)

    for idx, line in enumerate(lines):
        match = re.match(
            r"-\s*\[(?P<check>[ xX])\]\s*\*\*(?P<kind>Pattern|Decision|Gotcha|Failure):\*\*\s*(?P<desc>.+)$",
            line.strip(),
        )
        if not match:
            continue

        kind = match.group('kind').lower()
        desc = match.group('desc')
        desc = re.split(r"→|->", desc)[0].strip()
        if _is_placeholder(desc):
            continue

        title = desc
        items.append(ExtractItem(
            kind=kind,
            title=title,
            source='active/context.md (Extractable Knowledge)',
            details={},
            raw_text=desc,
        ))

        if match.group('check').lower() != 'x':
            updated_lines[idx] = line.replace('[ ]', '[x]', 1)

    if updated_lines != lines:
        updated_section = "\n".join(updated_lines)
        updated_content = content.replace(section, updated_section)
        return items, updated_content

    return items, None


def _parse_research_findings(content: str) -> List[ExtractItem]:
    section = _extract_section(content, 'Research Findings')
    if not section:
        return []

    items: List[ExtractItem] = []
    lines = section.splitlines()
    current_title = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer, current_title
        if not current_title:
            return
        title = current_title.strip()
        if _is_placeholder(title):
            return

        found = ''
        source = ''
        relevance = ''
        for buf_line in buffer:
            found_match = re.match(r"\*\*Found:\*\*\s*(.+)", buf_line.strip())
            if found_match:
                found = found_match.group(1).strip()
            source_match = re.match(r"\*\*Source:\*\*\s*(.+)", buf_line.strip())
            if source_match:
                source = source_match.group(1).strip()
            rel_match = re.match(r"\*\*Relevance:\*\*\s*(.+)", buf_line.strip())
            if rel_match:
                relevance = rel_match.group(1).strip()

        raw_text = " ".join([title, found, relevance]).strip()
        items.append(ExtractItem(
            kind=None,
            title=title,
            source='active/context.md (Research Findings)',
            details={'found': found, 'source': source, 'relevance': relevance},
            raw_text=raw_text,
        ))

    for line in lines:
        heading = re.match(r"###\s+Discovery\s+\d+:\s*(.+)", line.strip())
        if heading:
            flush()
            current_title = heading.group(1)
            buffer = []
            continue

        if current_title is not None:
            buffer.append(line)

    flush()
    return items


def _parse_key_insights(content: str) -> List[ExtractItem]:
    section = _extract_section(content, 'Key Insights')
    if not section:
        return []

    items: List[ExtractItem] = []
    for line in section.splitlines():
        match = re.match(r"\s*(?:\d+\.|[-*])\s+(.+)", line.strip())
        if not match:
            continue
        insight = match.group(1).strip()
        if _is_placeholder(insight):
            continue
        items.append(ExtractItem(
            kind=None,
            title=insight,
            source='active/context.md (Key Insights)',
            details={},
            raw_text=insight,
        ))
    return items


def _parse_decisions_task_plan(content: str) -> List[ExtractItem]:
    section = _extract_section(content, 'Decisions Made This Session')
    if not section:
        return []

    lines = section.splitlines()
    items: List[ExtractItem] = []
    current: Optional[ExtractItem] = None

    for line in lines:
        decision_match = re.match(r"-\s*\*\*Decision:\*\*\s*(.+)", line.strip())
        if decision_match:
            title = decision_match.group(1).strip()
            if not _is_placeholder(title):
                if current:
                    items.append(current)
                current = ExtractItem(
                    kind='decision',
                    title=title,
                    source='active/task_plan.md (Decisions)',
                    details={},
                    raw_text=title,
                )
            continue

        if current is None:
            continue

        why_match = re.match(r"-\s*\*\*Why:\*\*\s*(.+)", line.strip())
        if why_match:
            current.details['why'] = why_match.group(1).strip()
            continue

        rejected_match = re.match(r"-\s*\*\*Rejected:\*\*\s*(.+)", line.strip())
        if rejected_match:
            current.details['rejected'] = rejected_match.group(1).strip()
            continue

    if current:
        items.append(current)

    return items


def _append_entry(path: Path, entry: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
    with path.open('a', encoding='utf-8') as f:
        f.write(entry)


def _write_status(status: Dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATUS_FILE.open('w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)


def _format_common_metadata(timestamp: str, fp: str, draft_mode: bool, quality: float) -> str:
    lines = []
    if draft_mode:
        lines.append("**Status:** Candidate (auto-extracted)")
    lines.append(f"**Quality Score:** {quality:.2f}")
    lines.append(f"**Auto-Extracted:** {timestamp}")
    lines.append(f"**Auto-Fingerprint:** [auto:{fp}]")
    return "\n".join(lines) + "\n"


def _format_pattern(item: ExtractItem, timestamp: str, draft_mode: bool, quality: float) -> str:
    today = date.today().isoformat()
    fp = _fingerprint('pattern', item.title)
    metadata = _format_common_metadata(timestamp, fp, draft_mode, quality)
    found = item.details.get('found')
    relevance = item.details.get('relevance')
    lines = [
        "",
        f"## Pattern: {item.title}",
        metadata.rstrip(),
        f"**Established:** {today}",
        f"**Context:** Auto-extracted from {item.source}",
        f"**When to apply:** {item.title}",
    ]
    if found:
        lines.extend(["**Implementation:**", f"- {found}"])
    if relevance:
        lines.append(f"**Why it works:** {relevance}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _format_decision(item: ExtractItem, timestamp: str, draft_mode: bool, quality: float) -> str:
    today = date.today().isoformat()
    fp = _fingerprint('decision', item.title)
    metadata = _format_common_metadata(timestamp, fp, draft_mode, quality)
    why = item.details.get('why')
    rejected = item.details.get('rejected')
    lines = [
        "",
        f"## Decision: {item.title}",
        metadata.rstrip(),
        f"**Date:** {today}",
        f"**Context:** Auto-extracted from {item.source}",
        f"**Chosen:** {item.title}",
    ]
    if rejected:
        lines.append(f"**Rejected:** {rejected}")
    if why:
        lines.extend(["**Rationale:**", f"- {why}"])
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _format_gotcha(item: ExtractItem, timestamp: str, draft_mode: bool, quality: float) -> str:
    today = date.today().isoformat()
    fp = _fingerprint('gotcha', item.title)
    metadata = _format_common_metadata(timestamp, fp, draft_mode, quality)
    lines = [
        "",
        f"## Gotcha: {item.title}",
        metadata.rstrip(),
        f"**Discovered:** {today}",
        f"**Context:** Auto-extracted from {item.source}",
        f"**Surprise:** {item.title}",
    ]
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _format_failure(item: ExtractItem, timestamp: str, draft_mode: bool, quality: float) -> str:
    today = date.today().isoformat()
    fp = _fingerprint('failure', item.title)
    metadata = _format_common_metadata(timestamp, fp, draft_mode, quality)
    lines = [
        "",
        f"## Error: [Auto-Extracted] {item.title}",
        metadata.rstrip(),
        f"**First seen:** {today}",
        f"**Symptom:** {item.title}",
        f"**Context:** Auto-extracted from {item.source}",
    ]
    if item.details.get('found'):
        lines.append(f"**Evidence:** {item.details['found']}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _dedupe_keep_best(items: List[ExtractItem]) -> List[ExtractItem]:
    best_by_key: Dict[str, Tuple[ExtractItem, float]] = {}
    for item in items:
        sanitized = _sanitize_item(item)
        if not sanitized:
            continue
        kind = sanitized.kind or _classify_kind(sanitized.raw_text)
        quality = _item_quality(sanitized, kind)
        key = f"{kind}:{sanitized.title.lower()}"
        current = best_by_key.get(key)
        if current is None or quality > current[1]:
            best_by_key[key] = (sanitized, quality)

    return [item for item, _ in best_by_key.values()]


def extract(dry_run: bool = False) -> Dict:
    context_path = ACTIVE_DIR / 'context.md'
    task_plan_path = ACTIVE_DIR / 'task_plan.md'

    scope = config_loader.get('auto_extraction.scope', 'balanced')
    draft_mode = config_loader.get('auto_extraction.draft_mode', True)
    min_quality = float(config_loader.get('auto_extraction.min_quality', 0.55))
    max_items = int(config_loader.get('auto_extraction.max_items_per_run', 24))

    extracted_counts = {'pattern': 0, 'decision': 0, 'gotcha': 0, 'failure': 0}

    context_content = _load(context_path)
    task_plan_content = _load(task_plan_path)

    items: List[ExtractItem] = []
    updated_context = None

    extractables, updated_context = _parse_extractable_context(context_content)
    items.extend(extractables)
    items.extend(_parse_decisions_task_plan(task_plan_content))

    if scope in ('balanced', 'aggressive'):
        items.extend(_parse_research_findings(context_content))
        items.extend(_parse_key_insights(context_content))

    deduped_items = _dedupe_keep_best(items)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sources = sorted({item.source for item in deduped_items})

    accepted = 0
    filtered_low_quality = 0
    scored_items = []
    for item in deduped_items:
        kind = item.kind or _classify_kind(item.raw_text)
        quality = _item_quality(item, kind)
        scored_items.append((item, kind, quality))

    scored_items.sort(key=lambda row: row[2], reverse=True)

    for item, kind, quality in scored_items[:max_items]:
        if quality < min_quality:
            filtered_low_quality += 1
            continue

        fp = _fingerprint(kind, item.title)

        if kind == 'pattern':
            target = KNOWLEDGE_DIR / 'patterns.md'
            entry = _format_pattern(item, timestamp, draft_mode, quality)
        elif kind == 'decision':
            target = KNOWLEDGE_DIR / 'decisions.md'
            entry = _format_decision(item, timestamp, draft_mode, quality)
        elif kind == 'gotcha':
            target = KNOWLEDGE_DIR / 'gotchas.md'
            entry = _format_gotcha(item, timestamp, draft_mode, quality)
        elif kind == 'failure':
            target = KNOWLEDGE_DIR / 'failures.md'
            entry = _format_failure(item, timestamp, draft_mode, quality)
        else:
            continue

        if _already_present(target, fp):
            continue

        if not dry_run:
            _append_entry(target, entry)

        extracted_counts[kind] += 1
        accepted += 1

    if updated_context and not dry_run:
        _write(context_path, updated_context)

    status = {
        'last_run': timestamp,
        'counts': extracted_counts,
        'sources': sources,
        'scope': scope,
        'draft_mode': draft_mode,
        'dry_run': dry_run,
        'quality': {
            'min_quality': min_quality,
            'considered': len(scored_items),
            'accepted': accepted,
            'filtered_low_quality': filtered_low_quality,
        },
    }

    if not dry_run:
        _write_status(status)

    return status


def read_status() -> Dict:
    if not STATUS_FILE.exists():
        return {'status': 'never'}
    try:
        return json.loads(STATUS_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {'status': 'error'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Auto extract knowledge into knowledge/ files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be extracted')
    args = parser.parse_args()

    status = extract(dry_run=args.dry_run)

    print("Auto extraction summary:")
    counts = status.get('counts', {})
    for kind in ['pattern', 'decision', 'gotcha', 'failure']:
        print(f"  {kind}: {counts.get(kind, 0)}")

    quality = status.get('quality', {})
    print(f"  filtered_low_quality: {quality.get('filtered_low_quality', 0)}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Context Engine: Auto-Extractor
Automatically promotes discoveries/decisions to knowledge files.
"""

import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add scripts dir to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
from observation_types import ObservationClassifier, ObservationType

MEMORY_DIR = Path(__file__).parent.parent
ACTIVE_DIR = MEMORY_DIR / 'active'
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
STATE_FILE = KNOWLEDGE_DIR / '.auto_extracted.json'

CONTEXT_FILE = ACTIVE_DIR / 'context.md'
TASK_PLAN_FILE = ACTIVE_DIR / 'task_plan.md'

FILES_BY_TYPE = {
    ObservationType.DECISION: KNOWLEDGE_DIR / 'decisions.md',
    ObservationType.BUGFIX: KNOWLEDGE_DIR / 'failures.md',
    ObservationType.FEATURE: KNOWLEDGE_DIR / 'patterns.md',
    ObservationType.REFACTOR: KNOWLEDGE_DIR / 'patterns.md',
    ObservationType.DISCOVERY: KNOWLEDGE_DIR / 'gotchas.md',
    ObservationType.CHANGE: KNOWLEDGE_DIR / 'gotchas.md',
}


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding='utf-8')


def _is_placeholder(text: str) -> bool:
    if not text:
        return True
    lowered = text.lower()
    if "[" in text and "]" in text:
        return True
    for token in ("tbd", "todo", "placeholder", "???", "fill", "your task"):
        if token in lowered:
            return True
    return False


def _section(content: str, heading: str) -> str:
    pattern = rf'^## {re.escape(heading)}\n(.*?)(?=^## |\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _dedupe_key(kind: str, title: str, body: str) -> str:
    raw = f"{kind}\n{title}\n{body}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _load_state() -> Dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _save_state(state: Dict[str, str]):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _append_entry(path: Path, entry: str):
    if not path.exists():
        return
    content = path.read_text(encoding='utf-8')
    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + entry.strip() + "\n"
    path.write_text(content, encoding='utf-8')


def _format_pattern(title: str, body: str, source: str, date: str) -> str:
    bullets = "\n".join([f"- {line}" for line in body.splitlines() if line.strip()])
    if not bullets:
        bullets = "- Auto-extracted (verify details)"
    return f"""## Pattern: {title}
**Established:** {date}
**Used successfully:** 1 time
**Context:** {source}
**Implementation:**
{bullets}
**Why it works:** Auto-extracted (verify)
**Related:** 
"""


def _format_decision(title: str, context: str, why: str, rejected: str, date: str) -> str:
    rationale = why or "Auto-extracted (verify)"
    rejected_value = rejected or "Not specified"
    return f"""## Decision: {title}
**Date:** {date}
**Context:** {context}
**Chosen:** {title}
**Rejected:** {rejected_value}
**Rationale:**
- {rationale}
**Trade-offs:**
- Pro: (fill in)
- Con: (fill in)
**Mitigation:** (fill in)
**Related:** 
**Commit:** 
"""


def _format_gotcha(title: str, body: str, source: str, date: str) -> str:
    surprise = body.strip() if body.strip() else "Auto-extracted (verify details)"
    return f"""## Gotcha: {title}
**Discovered:** {date}
**Occurrences:** 1 time
**Context:** {source}
**Surprise:** {surprise}
**Why it happens:** (fill in)
**How to handle:** (fill in)
**Watch out:** (fill in)
**Related:** 
"""


def _format_failure(title: str, body: str, source: str, date: str) -> str:
    return f"""## Error: {title}
**First seen:** {date}
**Occurrences:** 1 tasks
**Symptom:** {body or title}
**Root cause:** (fill in)
**Solution:** (fill in)
**Files affected:** (fill in)
**Never do:** (fill in)
**Related:** 
"""


def _classify_to_file(title: str, body: str) -> ObservationType:
    classifier = ObservationClassifier()
    return classifier.classify(f"{title} {body}")


def _extract_extractable_knowledge(context: str) -> List[Tuple[str, str]]:
    items = []
    section = _section(context, "Extractable Knowledge")
    if not section:
        return items
    for line in section.splitlines():
        match = re.search(r'- \[(?P<checked>[ xX])\]\s+\*\*(?P<kind>Pattern|Failure|Decision|Gotcha):\*\*\s*(?P<desc>.+)', line)
        if not match:
            continue
        if match.group('checked').lower() != 'x':
            continue
        kind = match.group('kind').lower()
        desc = match.group('desc').strip()
        if _is_placeholder(desc):
            continue
        items.append((kind, desc))
    return items


def _extract_discoveries(context: str) -> List[Tuple[str, str]]:
    items = []
    section = _section(context, "Research Findings")
    if not section:
        return items
    blocks = re.split(r'^\s*###\s+Discovery\s*\d*\s*:\s*', section, flags=re.MULTILINE)
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        if _is_placeholder(title):
            continue
        found = ""
        source = ""
        relevance = ""
        for line in lines[1:]:
            if line.strip().startswith("**Found:**"):
                found = line.split("**Found:**", 1)[1].strip()
            elif line.strip().startswith("**Source:**"):
                source = line.split("**Source:**", 1)[1].strip()
            elif line.strip().startswith("**Relevance:**"):
                relevance = line.split("**Relevance:**", 1)[1].strip()
        body_parts = [p for p in (found, source and f"Source: {source}", relevance and f"Relevance: {relevance}") if p]
        body = "\n".join(body_parts)
        if _is_placeholder(body):
            continue
        items.append((title, body))
    return items


def _extract_key_insights(context: str) -> List[Tuple[str, str]]:
    items = []
    section = _section(context, "Key Insights")
    if not section:
        return items
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+\.\s+(.*)$', line) or re.match(r'^[-*]\s+(.*)$', line)
        if not match:
            continue
        insight = match.group(1).strip()
        if _is_placeholder(insight):
            continue
        title = insight.split('.')[0][:80]
        items.append((title, insight))
    return items


def _extract_decisions(task_plan: str) -> List[Tuple[str, str, str]]:
    items = []
    section = _section(task_plan, "Decisions Made This Session")
    if not section:
        return items
    blocks = re.split(r'^\s*-\s+\*\*Decision:\*\*\s*', section, flags=re.MULTILINE)
    for block in blocks[1:]:
        lines = [l.rstrip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0].strip()
        if _is_placeholder(title):
            continue
        why = ""
        rejected = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("- **Why:**"):
                why = stripped.split("**Why:**", 1)[1].strip()
            elif stripped.startswith("- **Rejected:**"):
                rejected = stripped.split("**Rejected:**", 1)[1].strip()
        if _is_placeholder(why) and _is_placeholder(rejected):
            why = ""
            rejected = ""
        items.append((title, why, rejected))
    return items


def _apply_solutions_from_error_log(task_plan: str, failures_path: Path) -> int:
    """Update auto-captured failures with solutions from the error log table."""
    table_match = re.search(r'## Live Error Log.*?\n\|.*?\n\|[-|]+\|(.*?)(##|\Z)', task_plan, re.DOTALL)
    if not table_match:
        return 0
    rows = []
    for line in table_match.group(1).splitlines():
        if not line.strip().startswith('|'):
            continue
        cols = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cols) < 4:
            continue
        error, _, status, solution = cols[:4]
        if not error or _is_placeholder(error):
            continue
        if status.lower() not in ("fixed", "resolved"):
            continue
        if _is_placeholder(solution):
            continue
        rows.append((error, solution))

    if not rows:
        return 0

    content = failures_path.read_text(encoding='utf-8') if failures_path.exists() else ""
    updated = 0
    for error, solution in rows:
        pattern = re.compile(rf'(\*\*Symptom:\*\*\s*{re.escape(error)}.*?\n\*\*Solution:\*\*\s*)(.*)', re.DOTALL)
        match = pattern.search(content)
        if not match:
            continue
        current_solution = match.group(2).splitlines()[0].strip()
        if "fill this in" not in current_solution:
            continue
        replacement = f"**Solution:** {solution}"
        content = pattern.sub(lambda m: f"{m.group(1)}{solution}", content, count=1)
        content = content.replace("**Status:** ⚠️ Needs solution (add solution once fixed)", "**Status:** ✅ Resolved")
        updated += 1

    if updated:
        failures_path.write_text(content, encoding='utf-8')
    return updated


def run_auto_extraction(dry_run: bool = False) -> Dict[str, int]:
    state = _load_state()
    date = datetime.now().strftime('%Y-%m-%d')
    summary = {"patterns": 0, "decisions": 0, "gotchas": 0, "failures": 0, "updated_failures": 0}

    context = _load_text(CONTEXT_FILE)
    task_plan = _load_text(TASK_PLAN_FILE)

    if not context and not task_plan:
        return summary

    # Update failures with solutions from task plan error log
    if task_plan and FILES_BY_TYPE[ObservationType.BUGFIX].exists():
        updated = _apply_solutions_from_error_log(task_plan, FILES_BY_TYPE[ObservationType.BUGFIX])
        summary["updated_failures"] += updated

    # Extract explicit extractable knowledge (checked items)
    for kind, desc in _extract_extractable_knowledge(context):
        kind_lower = kind.lower()
        title = desc.split("→")[0].strip()
        if _is_placeholder(title):
            continue
        body = desc
        key = _dedupe_key(kind_lower, title, body)
        if key in state:
            continue
        entry = ""
        source = "Auto-extracted from active/context.md (Extractable Knowledge)"
        if kind_lower == "pattern":
            entry = _format_pattern(title, body, source, date)
            target = FILES_BY_TYPE[ObservationType.FEATURE]
            summary["patterns"] += 1
        elif kind_lower == "decision":
            entry = _format_decision(title, source, "", "", date)
            target = FILES_BY_TYPE[ObservationType.DECISION]
            summary["decisions"] += 1
        elif kind_lower == "gotcha":
            entry = _format_gotcha(title, body, source, date)
            target = FILES_BY_TYPE[ObservationType.DISCOVERY]
            summary["gotchas"] += 1
        else:
            entry = _format_failure(title, body, source, date)
            target = FILES_BY_TYPE[ObservationType.BUGFIX]
            summary["failures"] += 1

        if not dry_run:
            _append_entry(target, entry)
            state[key] = datetime.now().isoformat()

    # Extract discoveries and key insights from context
    include_discoveries = config_loader.get('knowledge.auto_extract_discoveries', True)
    if include_discoveries and context:
        discoveries = _extract_discoveries(context) + _extract_key_insights(context)
        for title, body in discoveries:
            if _is_placeholder(title) or _is_placeholder(body):
                continue
            obs_type = _classify_to_file(title, body)
            target = FILES_BY_TYPE.get(obs_type, FILES_BY_TYPE[ObservationType.DISCOVERY])
            key = _dedupe_key(obs_type.value, title, body)
            if key in state:
                continue
            source = "Auto-extracted from active/context.md"
            if target.name == 'patterns.md':
                entry = _format_pattern(title, body, source, date)
                summary["patterns"] += 1
            elif target.name == 'decisions.md':
                entry = _format_decision(title, source, "", "", date)
                summary["decisions"] += 1
            elif target.name == 'failures.md':
                entry = _format_failure(title, body, source, date)
                summary["failures"] += 1
            else:
                entry = _format_gotcha(title, body, source, date)
                summary["gotchas"] += 1
            if not dry_run:
                _append_entry(target, entry)
                state[key] = datetime.now().isoformat()

    # Extract decisions from task_plan
    if task_plan:
        decisions = _extract_decisions(task_plan)
        for title, why, rejected in decisions:
            if _is_placeholder(title):
                continue
            key = _dedupe_key("decision", title, f"{why}\n{rejected}")
            if key in state:
                continue
            entry = _format_decision(title, "Auto-extracted from active/task_plan.md", why, rejected, date)
            if not dry_run:
                _append_entry(FILES_BY_TYPE[ObservationType.DECISION], entry)
                state[key] = datetime.now().isoformat()
            summary["decisions"] += 1

    if not dry_run:
        _save_state(state)

    return summary


def main():
    dry_run = '--dry-run' in sys.argv
    summary = run_auto_extraction(dry_run=dry_run)
    total = sum(summary.values())
    mode = "DRY RUN" if dry_run else "RUN"
    print(f"Auto-Extractor ({mode})")
    print(f"  patterns: {summary['patterns']}")
    print(f"  decisions: {summary['decisions']}")
    print(f"  gotchas: {summary['gotchas']}")
    print(f"  failures: {summary['failures']}")
    print(f"  failures updated: {summary['updated_failures']}")
    print(f"  total changes: {total}")


if __name__ == '__main__':
    main()

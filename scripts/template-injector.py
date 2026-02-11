#!/usr/bin/env python3
"""
Ultra-Planning V3: Template Injector
Auto-fill session templates with relevant knowledge from past sessions
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Optional

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager

# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
ACTIVE_DIR = MEMORY_DIR / 'active'
ARCHIVE_DIR = MEMORY_DIR / 'archive'
_SECTION_BOUNDARY = r'\n##\s+(?:Pattern|Error|Decision|Gotcha):'
_NOISE_VALUES = {'', 'tbd', 'todo', 'n/a', 'na', 'unknown'}


def extract_keywords(task_name: str) -> List[str]:
    """
    Extract keywords from task name using TF-IDF for better relevance

    Falls back to simple splitting if scikit-learn not available.
    """
    # Try TF-IDF extraction (more accurate)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Load knowledge base for TF-IDF context
        knowledge_corpus = []
        knowledge_files = [
            KNOWLEDGE_DIR / 'patterns.md',
            KNOWLEDGE_DIR / 'failures.md',
            KNOWLEDGE_DIR / 'decisions.md'
        ]

        for file_path in knowledge_files:
            if file_path.exists():
                content = cache_manager.load_file_cached(str(file_path))
                knowledge_corpus.append(content)

        if not knowledge_corpus:
            raise ValueError("No knowledge base available for TF-IDF")

        # Add task name to corpus
        knowledge_corpus.append(task_name)

        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(
            max_features=10,
            stop_words='english',
            ngram_range=(1, 2),  # Include bigrams (e.g., "jwt token")
            min_df=1
        )

        # Fit and transform
        tfidf_matrix = vectorizer.fit_transform(knowledge_corpus)

        # Get feature names (keywords)
        feature_names = vectorizer.get_feature_names_out()

        # Get TF-IDF scores for task name (last document)
        task_tfidf = tfidf_matrix[-1].toarray()[0]

        # Get top keywords with non-zero scores
        keyword_scores = [(feature_names[i], task_tfidf[i])
                          for i in range(len(feature_names))
                          if task_tfidf[i] > 0]

        # Sort by score and extract keywords
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        tfidf_keywords = [kw for kw, score in keyword_scores[:10]]

        # Also include simple split keywords for coverage
        simple_keywords = re.split(r'[-_\s/\\]+', task_name.lower())
        stop_words = {'add', 'create', 'update', 'fix', 'the', 'a', 'an', 'to', 'for', 'in', 'on', 'with'}
        simple_keywords = [k for k in simple_keywords if k and k not in stop_words]

        # Combine (dedupe while preserving order)
        all_keywords = []
        seen = set()
        for kw in tfidf_keywords + simple_keywords:
            if kw not in seen:
                all_keywords.append(kw)
                seen.add(kw)

        return all_keywords[:15]  # Top 15 keywords

    except (ImportError, ValueError):
        # Fallback to simple splitting
        keywords = re.split(r'[-_\s/\\]+', task_name.lower())

        # Remove common words
        stop_words = {'add', 'create', 'update', 'fix', 'the', 'a', 'an', 'to', 'for', 'in', 'on', 'with'}
        keywords = [k for k in keywords if k and k not in stop_words]

        return keywords


def _clean_value(value: str) -> str:
    cleaned = re.sub(r'\s+', ' ', (value or '').strip())
    if cleaned.lower() in _NOISE_VALUES:
        return ''
    return cleaned


def _extract_field(section: str, label: str) -> str:
    match = re.search(rf'\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n\*\*|\n##|\n---|\Z)', section, re.DOTALL)
    if not match:
        return ''

    value = _clean_value(match.group(1))
    value = value.split('\n')[0].strip()
    value = re.sub(r'^-\s*', '', value)
    return _clean_value(value)


def _extract_sections(content: str, section_prefix: str) -> List[str]:
    pattern = rf"({re.escape(section_prefix)}[^\n]*\n.*?)(?={_SECTION_BOUNDARY}|\Z)"
    return [m.group(1).strip() for m in re.finditer(pattern, content, flags=re.DOTALL)]


def _keyword_relevance(section: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.0
    lowered = section.lower()
    matches = sum(1 for kw in keywords if kw and kw in lowered)
    return matches / len(keywords)


def _section_quality(section: str) -> float:
    lowered = section.lower()
    score = 0.2

    if '**status:** candidate' in lowered or '**status:** draft' in lowered:
        score -= 0.2
    if any(token in lowered for token in ('**solution:**', '**root cause:**', '**rationale:**', '**why it works:**')):
        score += 0.25
    if any(token in lowered for token in ('**implementation:**', '**when to apply:**', '**chosen:**')):
        score += 0.2
    if '**auto-fingerprint:**' in lowered:
        score += 0.1

    if re.search(r'\b(tbd|todo|unknown)\b', lowered):
        score -= 0.35

    if len(section) >= 200:
        score += 0.1

    return max(0.0, min(1.0, score))


def _fit_score(relevance: float, quality: float) -> float:
    return (relevance * 0.65) + (quality * 0.35)


def _render_with_budget(lines: List[str], max_chars: int) -> str:
    if not lines:
        return ''

    rendered = []
    used = 0
    for line in lines:
        projected = used + len(line) + 1
        if projected > max_chars:
            rendered.append("- … more matches omitted (context budget limit)")
            break
        rendered.append(line)
        used = projected
    return '\n'.join(rendered)


def search_knowledge_file(
    filename: str,
    section_prefix: str,
    keywords: List[str],
    threshold: float = None,
    max_results: int = 3
) -> List[Dict]:
    """
    Search a knowledge file for relevant sections.

    Args:
        filename: Name of the file in KNOWLEDGE_DIR (e.g., 'patterns.md')
        section_prefix: The section header prefix (e.g., '## Pattern:')
        keywords: List of keywords to match against
        threshold: Minimum relevance score (default from config)
        max_results: Maximum number of results to return

    Returns:
        List of matching sections sorted by relevance
    """
    if threshold is None:
        threshold = config_loader.get('template_injection.relevance_threshold', 0.3)

    file_path = KNOWLEDGE_DIR / filename
    if not file_path.exists():
        return []

    content = cache_manager.load_file_cached(str(file_path))
    sections = _extract_sections(content, section_prefix)
    min_quality = float(config_loader.get('template_injection.min_quality', 0.35))

    results = []
    for section in sections:
        relevance = _keyword_relevance(section, keywords)
        quality = _section_quality(section)
        score = _fit_score(relevance, quality)

        if relevance >= threshold and quality >= min_quality:
            first_line = section.split('\n')[0].replace(section_prefix, '').strip()
            results.append({
                'name': first_line,
                'relevance': relevance,
                'quality': quality,
                'score': score,
                'content': section,
            })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:max_results]


def search_patterns(keywords: List[str], threshold: float = None) -> List[Dict]:
    """Search knowledge/patterns.md for relevant patterns"""
    return search_knowledge_file('patterns.md', '## Pattern:', keywords, threshold, max_results=3)


def search_failures(keywords: List[str], threshold: float = None) -> List[Dict]:
    """Search knowledge/failures.md for relevant errors to avoid"""
    return search_knowledge_file('failures.md', '## Error:', keywords, threshold, max_results=3)


def search_decisions(keywords: List[str], threshold: float = None) -> List[Dict]:
    """Search knowledge/decisions.md for relevant architectural choices"""
    return search_knowledge_file('decisions.md', '## Decision:', keywords, threshold, max_results=2)


def find_similar_archived_tasks(task_name: str) -> List[Path]:
    """Find similar tasks in archive based on name similarity"""
    if not ARCHIVE_DIR.exists():
        return []

    keywords = extract_keywords(task_name)
    similar_tasks = []

    for archive_dir in ARCHIVE_DIR.iterdir():
        if archive_dir.is_dir():
            dir_name_lower = archive_dir.name.lower()
            matches = sum(1 for kw in keywords if kw in dir_name_lower)
            if matches > 0:
                similar_tasks.append((archive_dir, matches))

    # Sort by relevance
    similar_tasks.sort(key=lambda x: x[1], reverse=True)
    return [task[0] for task in similar_tasks[:2]]


def extract_phases_from_archived_task(archive_dir: Path) -> List[str]:
    """Extract phases from archived task plan"""
    task_plan = archive_dir / 'task_plan.md'

    if not task_plan.exists():
        return []

    # Use cached file loading
    content = cache_manager.load_file_cached(str(task_plan))

    # Find phases section
    phases_match = re.search(r'## Phases\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if not phases_match:
        return []

    phases_text = phases_match.group(1)

    # Extract phase lines (- [ ] or - [x])
    phase_lines = re.findall(r'- \[[ x]\] (.+)', phases_text)

    # Clean up phase descriptions (remove status markers like ✓)
    cleaned_phases = []
    for phase in phase_lines:
        cleaned = re.sub(r'[✓✗❌]', '', phase).strip()
        if cleaned:
            cleaned_phases.append(cleaned)

    return cleaned_phases


def suggest_phases(task_name: str) -> List[str]:
    """Suggest likely phases based on similar archived tasks"""
    similar_tasks = find_similar_archived_tasks(task_name)

    if not similar_tasks:
        return []

    # Collect phases from similar tasks
    all_phases = []
    for task_dir in similar_tasks:
        phases = extract_phases_from_archived_task(task_dir)
        all_phases.extend(phases)

    # Count frequency and return unique phases
    phase_counts = {}
    for phase in all_phases:
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    # Sort by frequency
    sorted_phases = sorted(phase_counts.items(), key=lambda x: x[1], reverse=True)
    return [phase for phase, count in sorted_phases[:5]]


def format_patterns_for_template(patterns: List[Dict]) -> str:
    """Format patterns for insertion into template"""
    if not patterns:
        return "- No high-confidence patterns found yet"

    lines = []
    for p in patterns:
        lines.append(
            f"- **{p['name']}** (fit: {p['score']:.0%}, quality: {p['quality']:.0%})"
        )
        when_to_apply = _extract_field(p['content'], 'When to apply')
        implementation = _extract_field(p['content'], 'Implementation')
        why_works = _extract_field(p['content'], 'Why it works')

        if when_to_apply:
            lines.append(f"  Use when: {when_to_apply}")
        if implementation:
            lines.append(f"  Do: {implementation}")
        if why_works:
            lines.append(f"  Why: {why_works}")

    max_chars = int(config_loader.get('template_injection.max_render_chars', 1200))
    return _render_with_budget(lines, max_chars)


def format_failures_for_template(failures: List[Dict]) -> str:
    """Format failures for insertion into template"""
    if not failures:
        return "- No high-confidence failure patterns found yet"

    lines = []
    for f in failures:
        lines.append(
            f"- **{f['name']}** (fit: {f['score']:.0%}, quality: {f['quality']:.0%})"
        )
        symptom = _extract_field(f['content'], 'Symptom')
        root_cause = _extract_field(f['content'], 'Root cause')
        solution = _extract_field(f['content'], 'Solution')

        if symptom:
            lines.append(f"  Trigger: {symptom}")
        if root_cause:
            lines.append(f"  Cause: {root_cause}")
        if solution:
            lines.append(f"  Avoid by: {solution}")

    max_chars = int(config_loader.get('template_injection.max_render_chars', 1200))
    return _render_with_budget(lines, max_chars)


def format_decisions_for_template(decisions: List[Dict]) -> str:
    """Format decisions for insertion into template"""
    if not decisions:
        return "- No high-confidence related decisions found"

    lines = []
    for d in decisions:
        lines.append(
            f"- **{d['name']}** (fit: {d['score']:.0%}, quality: {d['quality']:.0%})"
        )
        chosen = _extract_field(d['content'], 'Chosen')
        rejected = _extract_field(d['content'], 'Rejected')
        rationale = _extract_field(d['content'], 'Rationale')

        if chosen:
            lines.append(f"  Choice: {chosen}")
        if rejected:
            lines.append(f"  Not chosen: {rejected}")
        if rationale:
            lines.append(f"  Why: {rationale}")

    max_chars = int(config_loader.get('template_injection.max_render_chars', 1200))
    return _render_with_budget(lines, max_chars)


def format_suggested_phases(phases: List[str]) -> str:
    """Format suggested phases for template"""
    if not phases:
        return "<!-- No similar tasks found. Define phases based on your goals. -->"

    lines = ["<!-- Suggested based on similar past tasks: -->"]
    for i, phase in enumerate(phases, 1):
        lines.append(f"- [ ] Phase {i}: {phase}")

    return '\n'.join(lines)


def inject_intelligence(task_name: str) -> None:
    """Main function to inject intelligence into templates"""
    print(f"🧠 Injecting intelligence for task: {task_name}")
    print()

    # Extract keywords
    keywords = extract_keywords(task_name)
    print(f"📎 Keywords: {', '.join(keywords)}")
    print()

    # Search knowledge base
    print("🔍 Searching knowledge base...")
    patterns = search_patterns(keywords)
    failures = search_failures(keywords)
    decisions = search_decisions(keywords)
    print(f"   Found: {len(patterns)} patterns, {len(failures)} failures, {len(decisions)} decisions")
    print()

    # Suggest phases
    print("📋 Analyzing similar past tasks...")
    suggested_phases = suggest_phases(task_name)
    if suggested_phases:
        print(f"   Found {len(suggested_phases)} common phases from similar tasks")
    else:
        print("   No similar tasks found (fresh territory!)")
    print()

    # Load template
    template_path = ACTIVE_DIR / 'TEMPLATE_task_plan.md'
    task_plan_path = ACTIVE_DIR / 'task_plan.md'

    if not task_plan_path.exists():
        print(f"❌ Error: {task_plan_path} not found. Run init-session.sh first!")
        sys.exit(1)

    # Use cached file loading
    template = cache_manager.load_file_cached(str(task_plan_path))

    # Inject patterns
    patterns_text = format_patterns_for_template(patterns)
    template = template.replace(
        '<!-- Auto-injected from knowledge/patterns.md -->',
        patterns_text
    )

    # Inject failures
    failures_text = format_failures_for_template(failures)
    template = template.replace(
        '<!-- Auto-injected from knowledge/failures.md -->',
        failures_text
    )

    # Inject decisions
    decisions_text = format_decisions_for_template(decisions)
    template = template.replace(
        '<!-- Auto-injected from knowledge/decisions.md -->',
        decisions_text
    )

    # Inject suggested phases (if section exists)
    if '<!-- Suggested phases will be auto-injected here -->' in template:
        phases_text = format_suggested_phases(suggested_phases)
        template = template.replace(
            '<!-- Suggested phases will be auto-injected here -->',
            phases_text
        )

    # Write back
    with open(task_plan_path, 'w') as f:
        f.write(template)

    print(f"✅ Template injected with intelligence!")
    print()
    print("📚 Pre-Task Intelligence:")
    print(f"   • {len(patterns)} relevant patterns loaded")
    print(f"   • {len(failures)} known errors to avoid")
    print(f"   • {len(decisions)} related decisions for context")
    if suggested_phases:
        print(f"   • {len(suggested_phases)} suggested phases from similar tasks")
    print()
    print(f"📝 Edit your plan: {task_plan_path}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: template-injector.py <task-name>")
        sys.exit(1)

    task_name = sys.argv[1]
    inject_intelligence(task_name)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Context Engine: Session Summarizer
Generates structured 5-field session summaries.

Summary Fields:
- request: What the user originally asked for
- investigated: Files/code/areas examined
- learned: Key discoveries made
- completed: What was accomplished
- next_steps: Pending work or follow-ups

Inspired by claude-mem's SessionSummaryRecord structure.
"""

import re
import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager


# ============================================================================
# Constants
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
ACTIVE_DIR = MEMORY_DIR / 'active'


# ============================================================================
# Session Summarizer
# ============================================================================

class SessionSummarizer:
    """Generates structured session summaries from active session files"""

    def __init__(self, active_dir: Optional[Path] = None):
        self.active_dir = active_dir or ACTIVE_DIR
        self.knowledge_dir = MEMORY_DIR / 'knowledge'

    def generate_summary(self) -> Dict[str, str]:
        """
        Generate a structured 5-field session summary.

        Returns:
            Dict with keys: request, investigated, learned, completed, next_steps
        """
        return {
            'request': self._extract_request(),
            'investigated': self._extract_investigated(),
            'learned': self._extract_learned(),
            'completed': self._extract_completed(),
            'next_steps': self._extract_next_steps()
        }

    def _extract_request(self) -> str:
        """Extract what the user originally asked for"""
        # First try: From prompts log (most accurate)
        prompts_log = self.active_dir / '.prompts_log.yaml'
        if prompts_log.exists():
            try:
                with open(prompts_log, 'r', encoding='utf-8') as f:
                    prompts = yaml.safe_load(f) or []
                if prompts and len(prompts) > 0:
                    first_request = prompts[0].get('request', '')
                    if first_request:
                        return self._truncate(first_request, 200)
            except Exception:
                pass

        # Second try: From task_plan.md Goal section
        task_plan = self.active_dir / 'task_plan.md'
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            # Look for Goal section
            goal_match = re.search(
                r'## Goal\s*\n+(.+?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if goal_match:
                goal = goal_match.group(1).strip()
                # Clean up template placeholders
                if not goal.startswith('[') and len(goal) > 10:
                    return self._truncate(goal, 200)

            # Try Task header
            task_match = re.search(r'# Task:\s*(.+)', content)
            if task_match:
                task_name = task_match.group(1).strip()
                if task_name and not task_name.startswith('['):
                    return task_name

        return 'No request recorded'

    def _extract_investigated(self) -> str:
        """Extract files/code/areas examined"""
        investigated = []

        # From context.md Code Locations table
        context = self.active_dir / 'context.md'
        if context.exists():
            content = cache_manager.load_file_cached(str(context))

            # Extract from Code Locations table
            # Pattern: | Component | File Path | Purpose | Notes |
            table_match = re.search(
                r'## Code Locations\s*\n+.*?\n\|[-|]+\|\s*\n(.*?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if table_match:
                rows = table_match.group(1).strip().split('\n')
                for row in rows:
                    # Extract file path (second column)
                    cells = [c.strip() for c in row.split('|') if c.strip()]
                    if len(cells) >= 2:
                        file_path = cells[1].strip()
                        if file_path and '/' in file_path and not file_path.startswith('['):
                            investigated.append(file_path)

            # Extract from discovery sources
            sources = re.findall(r'\*\*Source:\*\*\s*(.+)', content)
            for source in sources:
                source = source.strip()
                if source and not source.startswith('['):
                    investigated.append(source)

        # From task_plan.md Files Created/Modified
        task_plan = self.active_dir / 'task_plan.md'
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            # Extract file paths
            file_matches = re.findall(r'- \[.\]\s+([^\s-]+(?:\.[a-z]+)?)\s*-', content)
            for f in file_matches:
                if '/' in f or '.' in f:
                    investigated.append(f)

        # Deduplicate and limit
        investigated = list(dict.fromkeys(investigated))[:10]

        if investigated:
            return ', '.join(investigated)
        return 'Various areas explored'

    def _extract_learned(self) -> str:
        """Extract key discoveries made"""
        learned = []

        # From context.md Key Insights
        context = self.active_dir / 'context.md'
        if context.exists():
            content = cache_manager.load_file_cached(str(context))

            # Extract Key Insights section
            insights_match = re.search(
                r'## Key Insights\s*\n+(.+?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if insights_match:
                insights_text = insights_match.group(1)
                # Extract numbered or bulleted items
                items = re.findall(r'(?:\d+\.\s+|\*\s+|-\s+)(.+)', insights_text)
                for item in items:
                    item = item.strip()
                    if item and not item.startswith('['):
                        learned.append(self._truncate(item, 100))

            # Extract from Discovery sections
            discoveries = re.findall(r'\*\*Found:\*\*\s*(.+)', content)
            for d in discoveries:
                d = d.strip()
                if d and not d.startswith('['):
                    learned.append(self._truncate(d, 100))

        # From task_plan.md Decisions Made
        task_plan = self.active_dir / 'task_plan.md'
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            # Extract decisions
            decisions = re.findall(r'\*\*Decision:\*\*\s*(.+)', content)
            for d in decisions:
                d = d.strip()
                if d and not d.startswith('['):
                    learned.append(f"Decided: {self._truncate(d, 80)}")

        if learned:
            return '; '.join(learned[:3])
        return 'No specific learnings captured'

    def _extract_completed(self) -> str:
        """Extract what was accomplished"""
        completed = []

        # From task_plan.md Phases section
        task_plan = self.active_dir / 'task_plan.md'
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            # Extract completed phases (checked boxes)
            completed_phases = re.findall(r'- \[x\]\s+(?:Phase \d+:\s*)?(.+)', content, re.IGNORECASE)
            for phase in completed_phases:
                # Clean up the phase name
                phase = re.sub(r'\(Status:.*?\)', '', phase).strip()
                if phase and not phase.startswith('['):
                    completed.append(phase)

        # From Files Created/Modified (completed items)
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            files_match = re.search(
                r'## Files Created/Modified\s*\n+(.+?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if files_match:
                # Count completed files
                files_text = files_match.group(1)
                created_count = len(re.findall(r'- \[x\]', files_text))
                if created_count > 0:
                    completed.append(f"Modified {created_count} file(s)")

        if completed:
            return '; '.join(completed[:5])
        return 'Work in progress'

    def _extract_next_steps(self) -> str:
        """Extract pending work or follow-ups"""
        next_steps = []

        # From task_plan.md Next Steps section
        task_plan = self.active_dir / 'task_plan.md'
        if task_plan.exists():
            content = cache_manager.load_file_cached(str(task_plan))

            # Look for Next Steps section
            next_match = re.search(
                r'## Next Steps\s*\n+(.+?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if next_match:
                next_text = next_match.group(1)
                items = re.findall(r'(?:\d+\.\s+|\*\s+|-\s+)(.+)', next_text)
                for item in items:
                    item = item.strip()
                    if item and not item.startswith('[') and not item.startswith('<!--'):
                        next_steps.append(self._truncate(item, 100))

            # Extract incomplete phases
            pending_phases = re.findall(r'- \[ \]\s+(?:Phase \d+:\s*)?(.+)', content)
            for phase in pending_phases:
                phase = re.sub(r'\(Status:.*?\)', '', phase).strip()
                if phase and not phase.startswith('['):
                    next_steps.append(phase)

        # From context.md Technical Debt
        context = self.active_dir / 'context.md'
        if context.exists():
            content = cache_manager.load_file_cached(str(context))

            debt_match = re.search(
                r'## Technical Debt\s*\n+(.+?)(?=\n---|\n##|\Z)',
                content,
                re.DOTALL
            )
            if debt_match:
                debt_items = re.findall(r'- \[ \]\s+(.+)', debt_match.group(1))
                for item in debt_items:
                    if item and not item.startswith('['):
                        next_steps.append(f"Tech debt: {self._truncate(item, 80)}")

        if next_steps:
            return '; '.join(next_steps[:5])
        return 'Continue with remaining tasks'

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length, adding ellipsis if needed"""
        text = text.strip()
        if len(text) > max_len:
            return text[:max_len - 3] + '...'
        return text


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_structured_summary(active_dir: Optional[Path] = None) -> Dict[str, str]:
    """
    Generate a structured session summary.

    Args:
        active_dir: Optional path to active directory

    Returns:
        Dict with keys: request, investigated, learned, completed, next_steps
    """
    summarizer = SessionSummarizer(active_dir)
    return summarizer.generate_summary()


def format_summary_yaml(summary: Dict[str, str]) -> str:
    """Format summary as YAML string"""
    return yaml.dump(
        {'session_summary': summary},
        default_flow_style=False,
        allow_unicode=True,
        width=80
    )


def format_summary_markdown(summary: Dict[str, str]) -> str:
    """Format summary as Markdown"""
    return f"""## Session Summary

**Request:** {summary['request']}

**Investigated:** {summary['investigated']}

**Learned:** {summary['learned']}

**Completed:** {summary['completed']}

**Next Steps:** {summary['next_steps']}
"""


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI interface for session summarizer"""
    parser = argparse.ArgumentParser(
        description='Context Engine Session Summarizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Generate YAML summary
  %(prog)s --format markdown  # Generate Markdown summary
  %(prog)s --format json      # Generate JSON summary
        """
    )

    parser.add_argument(
        '--format', '-f',
        choices=['yaml', 'markdown', 'json'],
        default='yaml',
        help='Output format (default: yaml)'
    )
    parser.add_argument(
        '--active-dir',
        type=Path,
        help='Path to active directory'
    )
    parser.add_argument(
        '--field',
        choices=['request', 'investigated', 'learned', 'completed', 'next_steps'],
        help='Extract only a specific field'
    )

    args = parser.parse_args()

    # Generate summary
    summary = generate_structured_summary(args.active_dir)

    # Output specific field or full summary
    if args.field:
        print(summary[args.field])
    elif args.format == 'yaml':
        print(format_summary_yaml(summary))
    elif args.format == 'markdown':
        print(format_summary_markdown(summary))
    elif args.format == 'json':
        import json
        print(json.dumps({'session_summary': summary}, indent=2))


if __name__ == '__main__':
    main()

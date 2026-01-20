#!/usr/bin/env python3
"""
Context Engine: Knowledge Parser
Centralized module for parsing knowledge base files.

Eliminates code duplication across server.py, knowledge-indexer.py,
and vector-search.py by providing a single source of truth for
knowledge file parsing logic.
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Callable

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import cache_manager
from observation_types import ObservationType, ObservationClassifier, get_type_emoji


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class KnowledgeEntry:
    """Represents a single knowledge base entry."""
    id: str
    file: str
    title: str
    content: str
    preview: str
    obs_type: Optional[ObservationType] = None
    obs_emoji: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'file': self.file,
            'title': self.title,
            'content': self.content,
            'preview': self.preview,
            'obs_type': self.obs_type.value if self.obs_type else None,
            'obs_emoji': self.obs_emoji
        }


@dataclass
class KnowledgeFile:
    """Configuration for a knowledge file."""
    filename: str
    section_prefix: str

    @property
    def pattern(self) -> str:
        """Get regex pattern for splitting sections."""
        return r'\n' + re.escape(self.section_prefix)


# ============================================================================
# Constants
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'

# Knowledge file configurations (single source of truth)
KNOWLEDGE_FILES: List[KnowledgeFile] = [
    KnowledgeFile('patterns.md', '## Pattern:'),
    KnowledgeFile('failures.md', '## Error:'),
    KnowledgeFile('decisions.md', '## Decision:'),
    KnowledgeFile('gotchas.md', '## Gotcha:'),
]


# ============================================================================
# Core Parsing Functions
# ============================================================================

def parse_knowledge_file(
    filepath: Path,
    section_prefix: str,
    max_content_length: int = 500,
    max_preview_length: int = 200
) -> List[KnowledgeEntry]:
    """
    Parse a single knowledge file into entries.

    Args:
        filepath: Path to the knowledge file
        section_prefix: The markdown prefix that starts each section
        max_content_length: Maximum characters to include in content
        max_preview_length: Maximum characters for preview

    Returns:
        List of KnowledgeEntry objects
    """
    if not filepath.exists():
        return []

    content = cache_manager.load_file_cached(str(filepath))
    pattern = r'\n' + re.escape(section_prefix)
    splits = re.split(pattern, content)

    entries = []
    filename = filepath.name

    for i, section_content in enumerate(splits[1:], 1):
        lines = section_content.strip().split('\n')
        title = lines[0].strip() if lines else 'Untitled'

        # Extract preview (first non-empty, non-formatting line)
        preview = ''
        for line in lines[1:5]:
            line = line.strip()
            if line and not line.startswith('**') and not line.startswith('---'):
                preview = line[:max_preview_length]
                break

        entries.append(KnowledgeEntry(
            id=f'{filename.replace(".md", "")}_{i}',
            file=filename,
            title=title,
            content=section_content[:max_content_length],
            preview=preview
        ))

    return entries


def parse_all_knowledge_files(
    classify: bool = True,
    type_filter: Optional[str] = None
) -> List[KnowledgeEntry]:
    """
    Parse all knowledge files and optionally classify entries.

    Args:
        classify: Whether to classify entries by observation type
        type_filter: Optional filter by observation type value (e.g., 'bugfix')

    Returns:
        List of KnowledgeEntry objects
    """
    classifier = ObservationClassifier() if classify else None
    entries = []

    for kf in KNOWLEDGE_FILES:
        filepath = KNOWLEDGE_DIR / kf.filename
        file_entries = parse_knowledge_file(filepath, kf.section_prefix)

        for entry in file_entries:
            if classify and classifier:
                obs_type = classifier.classify(
                    f"{entry.title} {entry.preview}",
                    entry.file
                )
                entry.obs_type = obs_type
                entry.obs_emoji = get_type_emoji(obs_type)

            # Apply type filter
            if type_filter and type_filter != 'all':
                if entry.obs_type and entry.obs_type.value != type_filter:
                    continue

            entries.append(entry)

    return entries


def iter_knowledge_entries(
    classify: bool = False
) -> Iterator[KnowledgeEntry]:
    """
    Iterator over all knowledge entries (memory-efficient for large datasets).

    Args:
        classify: Whether to classify entries by observation type

    Yields:
        KnowledgeEntry objects
    """
    classifier = ObservationClassifier() if classify else None

    for kf in KNOWLEDGE_FILES:
        filepath = KNOWLEDGE_DIR / kf.filename

        for entry in parse_knowledge_file(filepath, kf.section_prefix):
            if classify and classifier:
                obs_type = classifier.classify(
                    f"{entry.title} {entry.preview}",
                    entry.file
                )
                entry.obs_type = obs_type
                entry.obs_emoji = get_type_emoji(obs_type)

            yield entry


# ============================================================================
# Search Functions
# ============================================================================

def search_knowledge(
    query: str,
    type_filter: Optional[str] = None,
    max_results: int = 20
) -> List[KnowledgeEntry]:
    """
    Search knowledge base by keyword.

    Args:
        query: Search query (case-insensitive)
        type_filter: Optional observation type filter
        max_results: Maximum results to return

    Returns:
        List of matching KnowledgeEntry objects
    """
    if not query or len(query) < 2:
        return []

    query_lower = query.lower()
    results = []

    for entry in iter_knowledge_entries(classify=True):
        # Search in title and content
        if query_lower in entry.title.lower() or query_lower in entry.content.lower():
            # Apply type filter
            if type_filter and type_filter != 'all':
                if entry.obs_type and entry.obs_type.value != type_filter:
                    continue

            results.append(entry)

            if len(results) >= max_results:
                break

    return results


# ============================================================================
# Statistics Functions
# ============================================================================

def count_entries(filename: str, section_prefix: str) -> int:
    """
    Count entries in a knowledge file.

    Args:
        filename: Name of the file (e.g., 'patterns.md')
        section_prefix: Section prefix to count

    Returns:
        Number of entries
    """
    filepath = KNOWLEDGE_DIR / filename
    if not filepath.exists():
        return 0

    content = cache_manager.load_file_cached(str(filepath))
    return len(re.findall(section_prefix, content, re.IGNORECASE))


def get_knowledge_stats() -> Dict[str, int]:
    """
    Get statistics for all knowledge files.

    Returns:
        Dict with counts per file and total
    """
    stats = {}
    total = 0

    for kf in KNOWLEDGE_FILES:
        key = kf.filename.replace('.md', '')
        count = count_entries(kf.filename, kf.section_prefix)
        stats[key] = count
        total += count

    stats['total'] = total
    return stats


def get_type_counts() -> Dict[str, int]:
    """
    Get counts by observation type.

    Returns:
        Dict mapping observation type values to counts
    """
    type_counts = {t.value: 0 for t in ObservationType}

    for entry in iter_knowledge_entries(classify=True):
        if entry.obs_type:
            type_counts[entry.obs_type.value] += 1

    return type_counts


# ============================================================================
# Utility Functions
# ============================================================================

def extract_section_titles(
    filename: str,
    section_prefix: str
) -> List[str]:
    """
    Extract just the titles from a knowledge file.

    Args:
        filename: Name of the file
        section_prefix: Section prefix pattern

    Returns:
        List of section titles
    """
    filepath = KNOWLEDGE_DIR / filename
    if not filepath.exists():
        return []

    content = cache_manager.load_file_cached(str(filepath))
    pattern = section_prefix + r'(.+)'

    return [
        match.group(1).strip()
        for match in re.finditer(pattern, content, re.IGNORECASE)
    ]


def get_knowledge_file_config(filename: str) -> Optional[KnowledgeFile]:
    """
    Get configuration for a specific knowledge file.

    Args:
        filename: Name of the file

    Returns:
        KnowledgeFile config or None
    """
    for kf in KNOWLEDGE_FILES:
        if kf.filename == filename:
            return kf
    return None


# ============================================================================
# Testing
# ============================================================================

def main():
    """Test knowledge parser functionality."""
    print("Context Engine: Knowledge Parser")
    print("=" * 50)
    print()

    # Test statistics
    stats = get_knowledge_stats()
    print("Knowledge Base Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    # Test parsing
    entries = parse_all_knowledge_files(classify=True)
    print(f"Parsed {len(entries)} total entries")
    print()

    # Show sample entries
    if entries:
        print("Sample entries:")
        for entry in entries[:3]:
            print(f"  {entry.obs_emoji} [{entry.obs_type.value if entry.obs_type else 'unknown'}] {entry.title[:40]}...")
    print()

    # Test type counts
    type_counts = get_type_counts()
    print("By observation type:")
    for obs_type, count in type_counts.items():
        if count > 0:
            emoji = get_type_emoji(ObservationType.from_string(obs_type))
            print(f"  {emoji} {obs_type}: {count}")
    print()

    print("Done!")


if __name__ == '__main__':
    main()

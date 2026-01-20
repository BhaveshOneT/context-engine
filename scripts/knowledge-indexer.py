#!/usr/bin/env python3
"""
Ultra-Planning V3: Knowledge Indexer
Auto-generate index.md with statistics, keywords, and cross-references
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Set

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager
from observation_types import ObservationType, ObservationClassifier, get_type_emoji

# Optional: semantic similarity for cross-references
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
VECTORS_DIR = KNOWLEDGE_DIR / 'vectors'


def count_sections(file_path: Path, pattern: str) -> int:
    """Count sections in a markdown file (with caching)"""
    if not file_path.exists():
        return 0

    # Use cached file loading
    content = cache_manager.load_file_cached(str(file_path))

    return len(re.findall(pattern, content, re.IGNORECASE))


def extract_section_titles(file_path: Path, pattern: str) -> List[str]:
    """Extract section titles from markdown file (with caching)"""
    if not file_path.exists():
        return []

    # Use cached file loading
    content = cache_manager.load_file_cached(str(file_path))

    titles = []
    for match in re.finditer(pattern + r'(.+)', content, re.IGNORECASE):
        title = match.group(1).strip()
        titles.append(title)

    return titles


def extract_keywords_from_text(text: str) -> Set[str]:
    """Extract meaningful keywords from text"""
    # Convert to lowercase
    text_lower = text.lower()

    # Remove markdown formatting
    text_clean = re.sub(r'[*_`#\[\]]', '', text_lower)

    # Extract words (3+ characters)
    words = re.findall(r'\b\w{3,}\b', text_clean)

    # Stop words to exclude
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
        'will', 'was', 'were', 'been', 'have', 'has', 'had', 'with',
        'from', 'this', 'that', 'when', 'where', 'what', 'which', 'who',
        'how', 'why', 'does', 'did', 'done', 'doing', 'use', 'used', 'using',
        'make', 'made', 'making', 'get', 'got', 'getting', 'set', 'about'
    }

    keywords = {w for w in words if w not in stop_words}

    return keywords


def build_keyword_index() -> Dict[str, List[tuple]]:
    """Build keyword -> [(file, section_title)] mapping"""
    keyword_index = defaultdict(list)

    knowledge_files = ['patterns.md', 'failures.md', 'decisions.md', 'gotchas.md']

    for filename in knowledge_files:
        file_path = KNOWLEDGE_DIR / filename
        if not file_path.exists():
            continue

        section_prefix = cache_manager.get_section_prefix(filename)
        content = cache_manager.load_file_cached(str(file_path))
        pattern = r'\n' + re.escape(section_prefix)

        sections = re.split(pattern, content)

        for section in sections[1:]:
            title = section.split('\n')[0].strip()
            keywords = extract_keywords_from_text(section)

            for keyword in keywords:
                keyword_index[keyword].append((filename, title))

    return keyword_index


def classify_sections_by_type() -> Dict[ObservationType, List[Dict]]:
    """Classify all knowledge sections by observation type"""
    classifier = ObservationClassifier()
    type_index = defaultdict(list)

    knowledge_files = ['patterns.md', 'failures.md', 'decisions.md', 'gotchas.md']

    for filename in knowledge_files:
        file_path = KNOWLEDGE_DIR / filename
        if not file_path.exists():
            continue

        section_prefix = cache_manager.get_section_prefix(filename)
        content = cache_manager.load_file_cached(str(file_path))
        pattern = r'\n' + re.escape(section_prefix)

        sections = re.split(pattern, content)

        for section in sections[1:]:
            title = section.split('\n')[0].strip()
            # Classify based on title and first 200 chars of content
            preview = section[:200]
            obs_type = classifier.classify(f"{title} {preview}", filename)

            type_index[obs_type].append({
                'file': filename,
                'title': title,
                'preview': preview[:60]
            })

    return type_index


def format_type_section(type_index: Dict[ObservationType, List[Dict]]) -> str:
    """Format the observation type index section"""
    lines = []

    # Sort types by count (descending)
    sorted_types = sorted(
        type_index.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    for obs_type, entries in sorted_types:
        emoji = get_type_emoji(obs_type)
        count = len(entries)
        lines.append(f"### {emoji} {obs_type.value.title()} ({count})")

        # Show top 5 entries for each type
        for entry in entries[:5]:
            lines.append(f"- [{entry['file']}] {entry['title']}")

        if count > 5:
            lines.append(f"- _...and {count - 5} more_")

        lines.append("")

    return '\n'.join(lines)


def find_cross_references(threshold: float = None) -> List[Dict]:
    """Find related entries using semantic similarity"""
    # Load threshold from config if not provided
    if threshold is None:
        threshold = config_loader.get('semantic_search.cross_reference_threshold', 0.75)

    if not NUMPY_AVAILABLE:
        return []

    cross_refs = []

    knowledge_files = ['patterns', 'failures', 'decisions', 'gotchas']

    # Load all embeddings
    embeddings_data = {}

    for file_stem in knowledge_files:
        embedding_file = VECTORS_DIR / f'{file_stem}.npy'
        metadata_file = VECTORS_DIR / f'{file_stem}.json'

        if not (embedding_file.exists() and metadata_file.exists()):
            continue

        try:
            embeddings = np.load(embedding_file)
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            embeddings_data[file_stem] = {
                'embeddings': embeddings,
                'sections': metadata['sections']
            }
        except:
            continue

    if not embeddings_data:
        return []

    # Compare all pairs
    all_items = []
    for file_stem, data in embeddings_data.items():
        for i, section in enumerate(data['sections']):
            all_items.append({
                'file': file_stem,
                'section': section,
                'embedding': data['embeddings'][i]
            })

    # Find similar pairs
    for i in range(len(all_items)):
        for j in range(i + 1, len(all_items)):
            item_a = all_items[i]
            item_b = all_items[j]

            # Skip same file comparisons (less interesting)
            if item_a['file'] == item_b['file']:
                continue

            # Calculate cosine similarity
            emb_a = item_a['embedding']
            emb_b = item_b['embedding']

            similarity = np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b))

            if similarity >= threshold:
                # Extract titles
                title_a = item_a['section']['preview'][:60]
                title_b = item_b['section']['preview'][:60]

                cross_refs.append({
                    'file_a': f"{item_a['file']}.md",
                    'title_a': title_a,
                    'file_b': f"{item_b['file']}.md",
                    'title_b': title_b,
                    'similarity': similarity
                })

    # Sort by similarity
    cross_refs.sort(key=lambda x: x['similarity'], reverse=True)

    return cross_refs[:10]  # Top 10


def format_keyword_section(keyword_index: Dict[str, List[tuple]], limit: int = 50) -> str:
    """Format keyword section with most common keywords"""
    # Sort by frequency
    sorted_keywords = sorted(keyword_index.items(), key=lambda x: len(x[1]), reverse=True)

    lines = []
    for keyword, locations in sorted_keywords[:limit]:
        # Group by file
        by_file = defaultdict(int)
        for filename, title in locations:
            by_file[filename] += 1

        # Format as: keyword (X in patterns.md, Y in failures.md)
        file_counts = ', '.join([f"{count} in {filename}" for filename, count in sorted(by_file.items())])
        lines.append(f"- **{keyword}** ({file_counts})")

    return '\n'.join(lines)


def format_cross_references(cross_refs: List[Dict]) -> str:
    """Format cross-references section"""
    if not cross_refs:
        return "_Run auto-embedder.py to enable semantic cross-references_"

    lines = []
    for ref in cross_refs:
        sim_pct = int(ref['similarity'] * 100)
        lines.append(f"- **{ref['file_a']}** ↔️ **{ref['file_b']}** ({sim_pct}% similar)")
        lines.append(f"  - {ref['title_a']}")
        lines.append(f"  - {ref['title_b']}")

    return '\n'.join(lines)


def generate_index():
    """Generate knowledge/index.md"""
    print("📇 Knowledge Indexer: Generating index.md...")
    print()

    # Count entries
    stats = {
        'patterns': count_sections(KNOWLEDGE_DIR / 'patterns.md', r'## Pattern:'),
        'failures': count_sections(KNOWLEDGE_DIR / 'failures.md', r'## Error:'),
        'decisions': count_sections(KNOWLEDGE_DIR / 'decisions.md', r'## Decision:'),
        'gotchas': count_sections(KNOWLEDGE_DIR / 'gotchas.md', r'## Gotcha:'),
    }

    total = sum(stats.values())

    print(f"📊 Statistics:")
    print(f"   • Patterns: {stats['patterns']}")
    print(f"   • Failures: {stats['failures']}")
    print(f"   • Decisions: {stats['decisions']}")
    print(f"   • Gotchas: {stats['gotchas']}")
    print(f"   • Total: {total}")
    print()

    # Build keyword index
    print("🔍 Extracting keywords...")
    keyword_index = build_keyword_index()
    print(f"   ✓ {len(keyword_index)} unique keywords")
    print()

    # Classify by observation type
    print("🏷️  Classifying by observation type...")
    type_index = classify_sections_by_type()
    type_counts = {obs_type.value: len(entries) for obs_type, entries in type_index.items()}
    print(f"   ✓ {sum(type_counts.values())} entries classified into {len(type_counts)} types")
    print()

    # Find cross-references
    print("🔗 Finding cross-references...")
    cross_refs = find_cross_references()
    if cross_refs:
        print(f"   ✓ {len(cross_refs)} related entries found")
    else:
        print("   ℹ️  Run auto-embedder.py first for semantic cross-references")
    print()

    # Generate index content
    index_content = f"""# Knowledge Index

**Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Auto-generated** by knowledge-indexer.py _(do not edit manually)_

---

## Statistics

- **Patterns documented:** {stats['patterns']}
- **Failures prevented:** {stats['failures']}
- **Decisions recorded:** {stats['decisions']}
- **Gotchas tracked:** {stats['gotchas']}
- **Total knowledge entries:** {total}

---

## Quick Access

### By Type
- [Patterns](patterns.md) - Successful approaches and reusable solutions
- [Failures](failures.md) - Known errors and how to fix them
- [Decisions](decisions.md) - Architectural choices and rationale
- [Gotchas](gotchas.md) - Surprising behaviors and edge cases

### Search Tools
- Keyword search: `./scripts/search-knowledge.sh "term"`
- Semantic search: `python3 scripts/vector-search.py "query"`
- Type-filtered: `./ce search-type "query" [type]`

---

## By Observation Type

{format_type_section(type_index)}

---

## Most Common Keywords

{format_keyword_section(keyword_index, limit=50)}

---

## Cross-References (Related Entries)

{format_cross_references(cross_refs)}

---

## How to Use This Index

1. **Find by keyword:** Use Ctrl+F or `search-knowledge.sh`
2. **Semantic search:** Use `vector-search.py` for concept-based search
3. **Browse by type:** Click quick access links above
4. **Discover connections:** Check cross-references for related entries

---

_This index is automatically updated when knowledge files change._
_To regenerate: `python3 scripts/knowledge-indexer.py`_
"""

    # Write index
    index_file = KNOWLEDGE_DIR / 'index.md'

    with open(index_file, 'w') as f:
        f.write(index_content)

    print(f"✅ Index generated: {index_file}")
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Ultra-Planning V3: Knowledge Indexer")
        print()
        print("Usage:")
        print("  knowledge-indexer.py          # Generate index")
        print("  knowledge-indexer.py --help   # Show this help")
        print()
        print("Automatically generates knowledge/index.md with:")
        print("  • Statistics on all knowledge entries")
        print("  • Keyword index for quick lookup")
        print("  • Cross-references between related entries")
        print()
        print("Optional: pip install numpy (for cross-references)")
        sys.exit(0)

    generate_index()


if __name__ == '__main__':
    main()

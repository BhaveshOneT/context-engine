#!/usr/bin/env python3
"""
Context Engine: Cache Manager
Simple LRU caching for files, models, and parsed data
Uses Python stdlib (functools.lru_cache) - no external dependencies
"""

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Optional, Any
import sys

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader


# ============================================================================
# File Caching
# ============================================================================

@lru_cache(maxsize=32)
def load_file_cached(file_path: str) -> str:
    """
    Load file contents with caching

    Args:
        file_path: Absolute path to file (must be string for hashability)

    Returns:
        File contents as string

    Note: Cache is invalidated if you need fresh data - use clear_file_cache()
    """
    path = Path(file_path)

    if not path.exists():
        return ""

    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


@lru_cache(maxsize=16)
def hash_file_cached(file_path: str) -> str:
    """
    Generate SHA256 hash of file with caching

    Args:
        file_path: Absolute path to file

    Returns:
        SHA256 hex digest
    """
    path = Path(file_path)

    if not path.exists():
        return ""

    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def clear_file_cache():
    """Clear all file-related caches"""
    load_file_cached.cache_clear()
    hash_file_cached.cache_clear()


def get_file_cache_info():
    """Get cache statistics for file operations"""
    return {
        'load_file': load_file_cached.cache_info(),
        'hash_file': hash_file_cached.cache_info()
    }


# ============================================================================
# Model Caching (Sentence Transformers)
# ============================================================================

@lru_cache(maxsize=2)
def load_model_cached(model_name: str) -> Any:
    """
    Load SentenceTransformer model with caching

    This is a HUGE performance win - models take 5-10s to load.
    With caching, subsequent loads are instant.

    Args:
        model_name: Model identifier (e.g., 'BAAI/bge-large-en-v1.5')

    Returns:
        Loaded SentenceTransformer model

    Note: Requires sentence-transformers installed
    """
    try:
        from sentence_transformers import SentenceTransformer

        # Load model (first time is slow, cached after)
        model = SentenceTransformer(model_name)
        return model

    except ImportError:
        raise ImportError(
            "sentence-transformers not installed. "
            "Install with: pip install sentence-transformers"
        )


def clear_model_cache():
    """Clear model cache (frees memory)"""
    load_model_cached.cache_clear()


def get_model_cache_info():
    """Get cache statistics for model loading"""
    return {
        'load_model': load_model_cached.cache_info()
    }


# ============================================================================
# Parsed Data Caching (Markdown Sections)
# ============================================================================

@lru_cache(maxsize=16)
def parse_sections_cached(file_path: str, file_hash: str) -> tuple:
    """
    Parse markdown file into sections with caching

    Cache key includes file hash to auto-invalidate when file changes.

    Args:
        file_path: Absolute path to markdown file
        file_hash: SHA256 hash of file (for cache invalidation)

    Returns:
        Tuple of section dicts (hashable for caching)

    Note: Returns tuple instead of list for hashability
    """
    import re

    path = Path(file_path)

    if not path.exists():
        return tuple()

    content = load_file_cached(file_path)

    # Determine section pattern based on file type
    if 'patterns' in path.name:
        pattern = r'\n## Pattern:'
        section_prefix = '## Pattern:'
    elif 'failures' in path.name:
        pattern = r'\n## Error:'
        section_prefix = '## Error:'
    elif 'decisions' in path.name:
        pattern = r'\n## Decision:'
        section_prefix = '## Decision:'
    elif 'gotchas' in path.name:
        pattern = r'\n## Gotcha:'
        section_prefix = '## Gotcha:'
    else:
        # Generic heading parsing
        pattern = r'\n## '
        section_prefix = '## '

    # Split into sections
    splits = re.split(pattern, content)

    sections = []
    for i, section in enumerate(splits[1:], 1):  # Skip first empty split
        section_dict = {
            'id': f'{path.stem}_section_{i}',
            'file': path.name,
            'content': section_prefix + section.strip(),
            'preview': section[:100].strip()
        }
        sections.append(section_dict)

    # Return as tuple for hashability
    return tuple(sections)


def clear_parsed_cache():
    """Clear parsed data cache"""
    parse_sections_cached.cache_clear()


def get_parsed_cache_info():
    """Get cache statistics for parsed data"""
    return {
        'parse_sections': parse_sections_cached.cache_info()
    }


# ============================================================================
# Cache Management
# ============================================================================

def clear_all_caches():
    """Clear all caches (files, models, parsed data)"""
    clear_file_cache()
    clear_model_cache()
    clear_parsed_cache()


def get_all_cache_stats():
    """Get statistics for all caches"""
    return {
        'files': get_file_cache_info(),
        'models': get_model_cache_info(),
        'parsed': get_parsed_cache_info()
    }


def print_cache_stats():
    """Print cache statistics in human-readable format"""
    stats = get_all_cache_stats()

    print("📊 Cache Statistics")
    print()

    print("Files:")
    for name, info in stats['files'].items():
        hit_rate = info.hits / (info.hits + info.misses) * 100 if (info.hits + info.misses) > 0 else 0
        print(f"  • {name}: {info.hits} hits, {info.misses} misses ({hit_rate:.1f}% hit rate)")

    print()
    print("Models:")
    for name, info in stats['models'].items():
        hit_rate = info.hits / (info.hits + info.misses) * 100 if (info.hits + info.misses) > 0 else 0
        print(f"  • {name}: {info.hits} hits, {info.misses} misses ({hit_rate:.1f}% hit rate)")

    print()
    print("Parsed Data:")
    for name, info in stats['parsed'].items():
        hit_rate = info.hits / (info.hits + info.misses) * 100 if (info.hits + info.misses) > 0 else 0
        print(f"  • {name}: {info.hits} hits, {info.misses} misses ({hit_rate:.1f}% hit rate)")

    print()


# ============================================================================
# Testing
# ============================================================================

def main():
    """Test cache manager"""
    print("Context Engine: Cache Manager")
    print()
    print("Testing caching functionality...")
    print()

    # Test file caching
    test_file = Path(__file__).parent.parent / 'config.yaml'

    if test_file.exists():
        print("Testing file cache:")

        # First load (cache miss)
        content1 = load_file_cached(str(test_file))
        print(f"  ✓ First load: {len(content1)} bytes")

        # Second load (cache hit)
        content2 = load_file_cached(str(test_file))
        print(f"  ✓ Second load: {len(content2)} bytes (cached)")

        # Verify same content
        assert content1 == content2, "Cache returned different content!"
        print(f"  ✓ Content matches")
        print()

    # Print statistics
    print_cache_stats()

    print("✅ Cache manager working correctly!")


if __name__ == '__main__':
    main()

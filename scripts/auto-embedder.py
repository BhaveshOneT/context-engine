#!/usr/bin/env python3
"""
Ultra-Planning V3: Auto-Embedder
Automatically generate vector embeddings when knowledge changes
"""

import os
import sys
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    print("❌ Error: Required libraries not installed")
    print("   Install with: pip install sentence-transformers numpy")
    sys.exit(1)


# Get project memory directory
MEMORY_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = MEMORY_DIR / 'knowledge'
VECTORS_DIR = KNOWLEDGE_DIR / 'vectors'

# Model for embeddings (load from config)
MODEL_NAME = config_loader.get('semantic_search.model', 'BAAI/bge-large-en-v1.5')


def hash_file(file_path: Path) -> str:
    """Generate SHA256 hash of file contents (cached)"""
    if not file_path.exists():
        return ""

    # Use cached hash function (avoid recomputing)
    return cache_manager.hash_file_cached(str(file_path))


def load_hash_cache() -> Dict[str, str]:
    """Load cached file hashes"""
    cache_file = VECTORS_DIR / '.hash_cache.json'

    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_hash_cache(cache: Dict[str, str]):
    """Save file hashes to cache"""
    cache_file = VECTORS_DIR / '.hash_cache.json'

    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=2)


def parse_sections(file_path: Path) -> List[Dict]:
    """Parse markdown file into sections (with caching)"""
    if not file_path.exists():
        return []

    # Use cached file loading
    content = cache_manager.load_file_cached(str(file_path))

    # Determine section pattern based on file type
    if 'patterns' in file_path.name:
        pattern = r'\n## Pattern:'
        section_prefix = '## Pattern:'
    elif 'failures' in file_path.name:
        pattern = r'\n## Error:'
        section_prefix = '## Error:'
    elif 'decisions' in file_path.name:
        pattern = r'\n## Decision:'
        section_prefix = '## Decision:'
    elif 'gotchas' in file_path.name:
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
        sections.append({
            'id': f'{file_path.stem}_section_{i}',
            'file': file_path.name,
            'content': section_prefix + section.strip(),
            'preview': section[:100].strip()
        })

    return sections


def embed_sections(sections: List[Dict], model: SentenceTransformer) -> List[np.ndarray]:
    """Generate embeddings for sections"""
    if not sections:
        return []

    texts = [s['content'] for s in sections]
    embeddings = model.encode(texts, show_progress_bar=True)

    return embeddings


def save_embeddings(file_path: Path, sections: List[Dict], embeddings: List[np.ndarray]):
    """Save embeddings to vectors directory"""
    # Create vectors directory if needed
    VECTORS_DIR.mkdir(exist_ok=True)

    # Save embeddings as .npy
    embedding_file = VECTORS_DIR / f'{file_path.stem}.npy'
    np.save(embedding_file, embeddings)

    # Save metadata as .json
    metadata_file = VECTORS_DIR / f'{file_path.stem}.json'
    metadata = {
        'source_file': file_path.name,
        'generated': datetime.now().isoformat(),
        'model': MODEL_NAME,
        'sections': sections,
        'embedding_count': len(embeddings)
    }

    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)


def check_and_embed_file(file_path: Path, model: SentenceTransformer, hash_cache: Dict[str, str], force: bool = False) -> bool:
    """Check if file needs embedding and embed if necessary"""
    file_key = str(file_path.relative_to(MEMORY_DIR))

    # Get current hash
    current_hash = hash_file(file_path)

    if not current_hash:
        return False

    # Check if embedding needed
    cached_hash = hash_cache.get(file_key, "")

    if current_hash == cached_hash and not force:
        print(f"   ✓ {file_path.name} - up to date")
        return False

    # Need to embed
    print(f"   🔮 {file_path.name} - generating embeddings...")

    sections = parse_sections(file_path)

    if not sections:
        print(f"      (No sections found, skipping)")
        return False

    # Generate embeddings
    embeddings = embed_sections(sections, model)

    # Save
    save_embeddings(file_path, sections, embeddings)

    # Update cache
    hash_cache[file_key] = current_hash

    print(f"      ✓ Embedded {len(sections)} sections")
    return True


def auto_embed_all(force: bool = False):
    """Auto-embed all knowledge files"""
    print("🔮 Auto-Embedder: Starting...")
    print()

    # Load model (with caching - 5-10s savings on subsequent runs!)
    print(f"📦 Loading model: {MODEL_NAME}")
    print("   (First run will download ~1GB, subsequent runs are instant with cache)")

    try:
        model = cache_manager.load_model_cached(MODEL_NAME)
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        sys.exit(1)

    print("   ✓ Model loaded")
    print()

    # Load hash cache
    hash_cache = load_hash_cache()

    # Knowledge files to embed
    knowledge_files = [
        KNOWLEDGE_DIR / 'patterns.md',
        KNOWLEDGE_DIR / 'failures.md',
        KNOWLEDGE_DIR / 'decisions.md',
        KNOWLEDGE_DIR / 'gotchas.md'
    ]

    # Check and embed each file
    print("📚 Checking knowledge files:")
    updated_count = 0

    for file_path in knowledge_files:
        if file_path.exists():
            if check_and_embed_file(file_path, model, hash_cache, force):
                updated_count += 1
        else:
            print(f"   - {file_path.name} - not found (skipping)")

    # Save updated cache
    save_hash_cache(hash_cache)

    print()
    print(f"✅ Auto-Embedder: Complete!")
    print(f"   • {updated_count} file(s) updated")
    print(f"   • Embeddings saved to: {VECTORS_DIR}")
    print()
    print("💡 Semantic search is now available:")
    print("   python3 scripts/vector-search.py \"your query\"")
    print()


def check_status():
    """Check embedding status of knowledge files"""
    print("🔮 Auto-Embedder: Status Check")
    print()

    hash_cache = load_hash_cache()

    knowledge_files = [
        KNOWLEDGE_DIR / 'patterns.md',
        KNOWLEDGE_DIR / 'failures.md',
        KNOWLEDGE_DIR / 'decisions.md',
        KNOWLEDGE_DIR / 'gotchas.md'
    ]

    needs_update = []
    up_to_date = []
    missing = []

    for file_path in knowledge_files:
        if not file_path.exists():
            missing.append(file_path.name)
            continue

        file_key = str(file_path.relative_to(MEMORY_DIR))
        current_hash = hash_file(file_path)
        cached_hash = hash_cache.get(file_key, "")

        if current_hash != cached_hash:
            needs_update.append(file_path.name)
        else:
            up_to_date.append(file_path.name)

    if up_to_date:
        print("✅ Up to date:")
        for name in up_to_date:
            print(f"   • {name}")
        print()

    if needs_update:
        print("⚠️  Needs embedding:")
        for name in needs_update:
            print(f"   • {name}")
        print()
        print("Run: python3 scripts/auto-embedder.py --embed")
        print()

    if missing:
        print("ℹ️  Missing files:")
        for name in missing:
            print(f"   • {name}")
        print()

    if not needs_update:
        print("✅ All knowledge files are embedded and up to date!")
        print()


def main():
    if len(sys.argv) < 2:
        check_status()
    elif sys.argv[1] == '--embed':
        auto_embed_all(force=False)
    elif sys.argv[1] == '--force':
        auto_embed_all(force=True)
    elif sys.argv[1] == '--status':
        check_status()
    else:
        print("Ultra-Planning V3: Auto-Embedder")
        print()
        print("Usage:")
        print("  auto-embedder.py              # Check status")
        print("  auto-embedder.py --embed      # Embed changed files")
        print("  auto-embedder.py --force      # Re-embed all files")
        print("  auto-embedder.py --status     # Check embedding status")
        print()
        print("Automatically generates vector embeddings for semantic search.")
        print()
        print("Requires: pip install sentence-transformers numpy")
        sys.exit(0)


if __name__ == '__main__':
    main()

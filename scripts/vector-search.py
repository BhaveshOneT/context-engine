#!/usr/bin/env python3
"""
Vector Semantic Search for Knowledge Base
Requires: pip install sentence-transformers numpy

Usage:
    python vector-search.py "how to handle authentication"
    python vector-search.py "query" --rerank    # With reranking (more accurate)
"""

import sys
import os
import json
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager
from observation_types import ObservationType, ObservationClassifier, get_type_emoji

# Try to import reranker (optional)
try:
    import reranker
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    print("❌ Error: Required packages not installed")
    print("Install with: pip install sentence-transformers numpy")
    sys.exit(1)

MEMORY_DIR = Path(os.environ.get("PROJECT_MEMORY_DIR", ".project-memory"))
if not MEMORY_DIR.exists():
    # Try current directory's context-engine
    MEMORY_DIR = Path(__file__).parent.parent

VECTOR_DIR = MEMORY_DIR / "knowledge" / "vectors"

# Load model name from config (upgraded to BGE-M3 for better accuracy)
MODEL_NAME = config_loader.get('semantic_search.model', 'BAAI/bge-m3')


def init_model():
    """Initialize the BGE embedding model (with caching)"""
    print(f"Loading model: {MODEL_NAME}...")
    # Use cached model loading (saves 5-10s on subsequent loads)
    model = cache_manager.load_model_cached(MODEL_NAME)
    print("✓ Model loaded")
    return model


def generate_embeddings():
    """Generate embeddings for all knowledge base files"""
    model = init_model()
    knowledge_dir = MEMORY_DIR / "knowledge"
    VECTOR_DIR.mkdir(exist_ok=True)

    files = ["patterns", "failures", "decisions", "gotchas"]

    print("\n🧠 Generating embeddings...")

    for name in files:
        filepath = knowledge_dir / f"{name}.md"
        if not filepath.exists():
            continue

        # Use cached file loading and get section prefix from cache_manager
        content = cache_manager.load_file_cached(str(filepath))
        section_prefix = cache_manager.get_section_prefix(filepath.name)

        # Parse sections using the same logic as cache_manager
        import re
        pattern = r'\n' + re.escape(section_prefix)
        splits = re.split(pattern, content)

        sections = []
        for section in splits[1:]:
            header = section_prefix + section.split('\n')[0].strip()
            full_content = section_prefix + section.strip()
            sections.append({
                "header": header,
                "content": full_content,
            })

        if not sections:
            print(f"  ⊘ {name}.md: No content to embed")
            continue

        texts = [s["content"] for s in sections]
        embeddings = model.encode(texts, show_progress_bar=False)

        vector_data = {
            "file": str(filepath),
            "sections": [
                {
                    "header": s["header"],
                    "content": s["content"][:500],
                    "embedding": emb.tolist(),
                }
                for s, emb in zip(sections, embeddings)
            ],
        }

        vector_file = VECTOR_DIR / f"{name}.json"
        with open(vector_file, "w") as f:
            json.dump(vector_data, f)

        print(f"  ✓ {name}.md: {len(sections)} sections embedded")

    print("\n✅ Embeddings generated and saved")


def search_semantic(query, threshold=0.7, use_reranking=False, top_k=10, obs_type=None):
    """
    Search knowledge base using semantic similarity

    Args:
        query: Search query
        threshold: Minimum similarity score (for vector search)
        use_reranking: Enable two-stage search with reranking (more accurate)
        top_k: Number of results to return
        obs_type: Filter by observation type (decision, bugfix, feature, etc.)

    Two-stage search (when use_reranking=True):
        Stage 1: Fast vector search → top 50 candidates
        Stage 2: Cross-encoder reranking → top 10 precise results
    """
    classifier = ObservationClassifier()
    if not VECTOR_DIR.exists():
        print("❌ No embeddings found. Run with --generate first")
        return

    model = init_model()
    query_embedding = model.encode(query)

    print(f"\n🔍 Searching for: \"{query}\"")
    if obs_type:
        print(f"Filter: {obs_type} observation type")
    if use_reranking and RERANKER_AVAILABLE:
        print(f"Mode: Two-stage search (vector + reranking)")
        rerank_top_k = config_loader.get('semantic_search.reranker_top_k', 50)
        print(f"Stage 1: Vector search (top {rerank_top_k})")
        print(f"Stage 2: Cross-encoder reranking (top {top_k})")
    else:
        print(f"Mode: Vector search only")
        print(f"Similarity threshold: {threshold}")
    print("=" * 60)

    results = []

    # Stage 1: Vector search
    # Search all vector files
    for vector_file in VECTOR_DIR.glob("*.json"):
        with open(vector_file, "r") as f:
            vector_data = json.load(f)

        file_type = vector_file.stem

        for section in vector_data["sections"]:
            section_embedding = np.array(section["embedding"])
            similarity = np.dot(query_embedding, section_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(section_embedding)
            )

            if similarity >= threshold:
                # Classify observation type
                section_obs_type = classifier.classify(
                    f"{section['header']} {section['content'][:200]}",
                    f"{file_type}.md"
                )

                # Apply type filter if specified
                if obs_type and obs_type != 'all':
                    try:
                        filter_type = ObservationType.from_string(obs_type)
                        if section_obs_type != filter_type:
                            continue
                    except:
                        pass

                results.append(
                    {
                        "type": file_type,
                        "obs_type": section_obs_type,
                        "header": section["header"],
                        "content": section["content"],
                        "similarity": similarity,
                        "score": similarity,  # For reranker compatibility
                    }
                )

    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    # Stage 2: Reranking (if enabled)
    if use_reranking and RERANKER_AVAILABLE and results:
        rerank_top_k = config_loader.get('semantic_search.reranker_top_k', 50)
        candidates = results[:rerank_top_k]

        print(f"\n⚡ Reranking {len(candidates)} candidates...")
        results = reranker.rerank_results(query, candidates, top_k=top_k)
        print(f"✓ Reranked to top {len(results)} results")
    elif use_reranking and not RERANKER_AVAILABLE:
        print("\n⚠️  Reranking requested but not available (using vector search only)")
        results = results[:top_k]
    else:
        results = results[:top_k]

    if not results:
        print("\nNo matches found above threshold.")
        print(f"\nTry:")
        print(f"  • Lower threshold: --threshold 0.6")
        print(f"  • Different query terms")
        if not use_reranking:
            print(f"  • Enable reranking: --rerank (more accurate)")
        return

    # Display results
    print("\n")
    for i, result in enumerate(results, 1):
        # Use observation type emoji if available
        if 'obs_type' in result:
            type_emoji = get_type_emoji(result['obs_type'])
            type_label = result['obs_type'].value.upper()
        else:
            icon = {"patterns": "✓", "failures": "⚠️", "decisions": "🤔", "gotchas": "💡"}
            type_emoji = icon.get(result['type'], '•')
            type_label = result['type'].upper()
        print(f"{i}. {type_emoji} [{type_label}] {result['type']}")

        # Show both vector and rerank scores if available
        if 'rerank_score' in result:
            print(f"   Rerank Score: {result['rerank_score']:.3f} (vector: {result.get('vector_score', 0):.3f})")
        else:
            print(f"   Similarity: {result['similarity']:.3f}")

        print(f"   {result['header']}")
        print(f"   {'-' * 60}")
        # Show first 200 chars of content
        preview = result["content"][:200].replace("\n", " ")
        print(f"   {preview}...")
        print()

    print(f"{'-' * 60}")
    print(f"Found {len(results)} relevant matches")


def main():
    if len(sys.argv) < 2:
        print("Context Engine: Vector Semantic Search")
        print()
        print("Usage:")
        print(f"  {sys.argv[0]} --generate              # Generate embeddings")
        print(f"  {sys.argv[0]} \"search query\"          # Semantic search")
        print(f"  {sys.argv[0]} \"query\" --rerank         # Two-stage search (more accurate)")
        print(f"  {sys.argv[0]} \"query\" --threshold 0.6  # Custom threshold")
        print(f"  {sys.argv[0]} \"query\" --type decision  # Filter by observation type")
        print()
        print("Options:")
        print("  --rerank        Enable two-stage search (vector + cross-encoder)")
        print("  --threshold N   Similarity threshold (0.0-1.0, default: 0.7)")
        print("  --top-k N       Number of results (default: 10)")
        print("  --type TYPE     Filter by observation type")
        print()
        print("Observation Types:")
        print("  decision, bugfix, feature, refactor, discovery, change")
        print()
        print("Examples:")
        print("  ./ce vsearch \"jwt authentication\"")
        print("  ./ce vsearch \"jwt authentication\" --rerank")
        print("  ./ce vsearch \"fix errors\" --type bugfix")
        sys.exit(1)

    if sys.argv[1] == "--generate":
        generate_embeddings()
    else:
        query = sys.argv[1]
        threshold = 0.7
        use_reranking = False
        top_k = 10
        obs_type = None

        if "--threshold" in sys.argv:
            idx = sys.argv.index("--threshold")
            threshold = float(sys.argv[idx + 1])

        if "--rerank" in sys.argv or "--reranking" in sys.argv:
            use_reranking = True

        if "--top-k" in sys.argv:
            idx = sys.argv.index("--top-k")
            top_k = int(sys.argv[idx + 1])

        if "--type" in sys.argv:
            idx = sys.argv.index("--type")
            obs_type = sys.argv[idx + 1]

        search_semantic(query, threshold, use_reranking, top_k, obs_type)


if __name__ == "__main__":
    main()

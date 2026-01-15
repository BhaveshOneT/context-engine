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

    files = {
        "patterns": knowledge_dir / "patterns.md",
        "failures": knowledge_dir / "failures.md",
        "decisions": knowledge_dir / "decisions.md",
        "gotchas": knowledge_dir / "gotchas.md",
    }

    print("\n🧠 Generating embeddings...")

    for name, filepath in files.items():
        if not filepath.exists():
            continue

        # Read file and split by sections (## headers)
        with open(filepath, "r") as f:
            content = f.read()

        # Split by ## Pattern: or ## Error: etc
        sections = []
        current_section = []
        current_header = None

        for line in content.split("\n"):
            if line.startswith("## ") and any(
                keyword in line
                for keyword in ["Pattern:", "Error:", "Decision:", "Gotcha:"]
            ):
                if current_section and current_header:
                    sections.append(
                        {
                            "header": current_header,
                            "content": "\n".join(current_section),
                        }
                    )
                current_header = line
                current_section = [line]
            else:
                current_section.append(line)

        # Add last section
        if current_section and current_header:
            sections.append(
                {"header": current_header, "content": "\n".join(current_section)}
            )

        if not sections:
            print(f"  ⊘ {name}.md: No content to embed")
            continue

        # Generate embeddings
        texts = [s["content"] for s in sections]
        embeddings = model.encode(texts, show_progress_bar=False)

        # Save embeddings and metadata
        vector_data = {
            "file": str(filepath),
            "sections": [
                {
                    "header": s["header"],
                    "content": s["content"][:500],  # Store first 500 chars
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


def search_semantic(query, threshold=0.7, use_reranking=False, top_k=10):
    """
    Search knowledge base using semantic similarity

    Args:
        query: Search query
        threshold: Minimum similarity score (for vector search)
        use_reranking: Enable two-stage search with reranking (more accurate)
        top_k: Number of results to return

    Two-stage search (when use_reranking=True):
        Stage 1: Fast vector search → top 50 candidates
        Stage 2: Cross-encoder reranking → top 10 precise results
    """
    if not VECTOR_DIR.exists():
        print("❌ No embeddings found. Run with --generate first")
        return

    model = init_model()
    query_embedding = model.encode(query)

    print(f"\n🔍 Searching for: \"{query}\"")
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
                results.append(
                    {
                        "type": file_type,
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
        icon = {"patterns": "✓", "failures": "⚠️", "decisions": "🤔", "gotchas": "💡"}
        print(f"{i}. {icon.get(result['type'], '•')} {result['type'].upper()}")

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
        print()
        print("Options:")
        print("  --rerank        Enable two-stage search (vector + cross-encoder)")
        print("  --threshold N   Similarity threshold (0.0-1.0, default: 0.7)")
        print("  --top-k N       Number of results (default: 10)")
        print()
        print("Examples:")
        print("  ./ce vsearch \"jwt authentication\"")
        print("  ./ce vsearch \"jwt authentication\" --rerank")
        sys.exit(1)

    if sys.argv[1] == "--generate":
        generate_embeddings()
    else:
        query = sys.argv[1]
        threshold = 0.7
        use_reranking = False
        top_k = 10

        if "--threshold" in sys.argv:
            idx = sys.argv.index("--threshold")
            threshold = float(sys.argv[idx + 1])

        if "--rerank" in sys.argv or "--reranking" in sys.argv:
            use_reranking = True

        if "--top-k" in sys.argv:
            idx = sys.argv.index("--top-k")
            top_k = int(sys.argv[idx + 1])

        search_semantic(query, threshold, use_reranking, top_k)


if __name__ == "__main__":
    main()

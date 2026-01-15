#!/usr/bin/env python3
"""
Context Engine: Reranker
Two-stage search: Fast vector search → Precise cross-encoder reranking
Standard RAG pattern for improved search accuracy
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import config_loader
import cache_manager

try:
    from sentence_transformers import CrossEncoder
    import numpy as np
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False


# ============================================================================
# Reranker (Cross-Encoder)
# ============================================================================

def load_reranker_model() -> CrossEncoder:
    """
    Load cross-encoder model for reranking

    Cross-encoders are more accurate than bi-encoders (vector search)
    but slower, so we use them only on top candidates.

    Returns:
        Loaded CrossEncoder model

    Raises:
        ImportError: If sentence-transformers not installed
    """
    if not RERANKER_AVAILABLE:
        raise ImportError(
            "Reranker requires sentence-transformers. "
            "Install with: pip install sentence-transformers"
        )

    # Load model name from config
    model_name = config_loader.get(
        'semantic_search.reranker_model',
        'cross-encoder/ms-marco-MiniLM-L-6-v2'
    )

    # Load model (this is also cached if using cache_manager)
    model = CrossEncoder(model_name)
    return model


def rerank_results(
    query: str,
    candidates: List[Dict],
    top_k: int = None
) -> List[Dict]:
    """
    Rerank candidates using cross-encoder for higher precision

    Two-stage search pattern:
    1. Vector search provides fast recall (top 50 candidates)
    2. Cross-encoder provides precise ranking (top 10 results)

    Args:
        query: Search query
        candidates: List of candidate results from vector search
        top_k: Number of results to return (default from config)

    Returns:
        Reranked results with scores

    Example:
        >>> candidates = vector_search("jwt authentication", top_k=50)
        >>> results = rerank_results("jwt authentication", candidates, top_k=10)
    """
    if not RERANKER_AVAILABLE:
        # Fallback: return candidates as-is
        return candidates[:top_k] if top_k else candidates

    if not candidates:
        return []

    # Load config settings
    if top_k is None:
        top_k = config_loader.get('semantic_search.final_top_k', 10)

    # Load reranker model
    try:
        model = load_reranker_model()
    except Exception as e:
        print(f"Warning: Failed to load reranker: {e}")
        return candidates[:top_k]

    # Prepare query-candidate pairs
    pairs = []
    for candidate in candidates:
        # Extract text content for scoring
        text = candidate.get('content', '') or candidate.get('text', '')
        pairs.append([query, text])

    # Score all pairs
    try:
        scores = model.predict(pairs)
    except Exception as e:
        print(f"Warning: Reranking failed: {e}")
        return candidates[:top_k]

    # Combine candidates with new scores
    reranked = []
    for i, candidate in enumerate(candidates):
        candidate_copy = candidate.copy()
        candidate_copy['rerank_score'] = float(scores[i])
        # Keep original vector score for reference
        if 'score' in candidate:
            candidate_copy['vector_score'] = candidate['score']
        candidate_copy['score'] = float(scores[i])  # Use rerank score as primary
        reranked.append(candidate_copy)

    # Sort by rerank score (descending)
    reranked.sort(key=lambda x: x['rerank_score'], reverse=True)

    return reranked[:top_k]


def hybrid_search(
    query: str,
    vector_candidates: List[Dict],
    keyword_candidates: List[Dict] = None,
    top_k: int = None
) -> List[Dict]:
    """
    Hybrid search combining vector search and optional keyword search

    Args:
        query: Search query
        vector_candidates: Results from vector search
        keyword_candidates: Optional results from keyword search
        top_k: Number of final results

    Returns:
        Combined and reranked results
    """
    # Combine candidates (if keyword results provided)
    all_candidates = vector_candidates[:]

    if keyword_candidates:
        # Merge, removing duplicates by content hash
        seen_hashes = set()
        for candidate in vector_candidates:
            content = candidate.get('content', '') or candidate.get('text', '')
            seen_hashes.add(hash(content))

        for candidate in keyword_candidates:
            content = candidate.get('content', '') or candidate.get('text', '')
            if hash(content) not in seen_hashes:
                all_candidates.append(candidate)
                seen_hashes.add(hash(content))

    # Rerank combined candidates
    return rerank_results(query, all_candidates, top_k)


# ============================================================================
# Similarity Scoring Utilities
# ============================================================================

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors

    Args:
        vec_a: First vector
        vec_b: Second vector

    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not RERANKER_AVAILABLE:
        return 0.0

    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def batch_similarity(
    query_embedding: np.ndarray,
    candidate_embeddings: np.ndarray
) -> np.ndarray:
    """
    Calculate cosine similarity for a query against many candidates

    Optimized batch calculation using numpy.

    Args:
        query_embedding: Query vector (1D)
        candidate_embeddings: Candidate vectors (2D array)

    Returns:
        Array of similarity scores
    """
    if not RERANKER_AVAILABLE:
        return np.array([])

    # Normalize query
    query_norm = query_embedding / np.linalg.norm(query_embedding)

    # Normalize candidates
    candidate_norms = candidate_embeddings / np.linalg.norm(
        candidate_embeddings,
        axis=1,
        keepdims=True
    )

    # Batch cosine similarity
    similarities = np.dot(candidate_norms, query_norm)

    return similarities


# ============================================================================
# Testing & CLI
# ============================================================================

def test_reranker():
    """Test reranker functionality"""
    print("Context Engine: Reranker Test")
    print()

    if not RERANKER_AVAILABLE:
        print("❌ sentence-transformers not installed")
        print("   Install with: pip install sentence-transformers")
        return

    print("Testing reranker model loading...")
    try:
        model = load_reranker_model()
        print(f"✅ Reranker loaded: {model}")
        print()
    except Exception as e:
        print(f"❌ Failed to load reranker: {e}")
        return

    # Test with sample candidates
    print("Testing reranking with sample data...")
    query = "how to fix jwt token expiration"

    candidates = [
        {
            'content': 'JWT tokens expire after 1 hour. Use refresh tokens to get new access tokens.',
            'file': 'patterns.md',
            'score': 0.75
        },
        {
            'content': 'Database connection timeout errors can be resolved by increasing pool size.',
            'file': 'failures.md',
            'score': 0.70
        },
        {
            'content': 'To handle token expiration, implement automatic token refresh on 401 errors.',
            'file': 'patterns.md',
            'score': 0.68
        }
    ]

    print(f"Query: '{query}'")
    print(f"Candidates: {len(candidates)}")
    print()

    # Rerank
    reranked = rerank_results(query, candidates, top_k=3)

    print("Results (reranked):")
    for i, result in enumerate(reranked, 1):
        print(f"{i}. Score: {result['rerank_score']:.3f}")
        print(f"   File: {result['file']}")
        print(f"   Content: {result['content'][:80]}...")
        print()

    print("✅ Reranker working correctly!")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        test_reranker()
    else:
        print("Context Engine: Reranker")
        print()
        print("Two-stage search for improved accuracy:")
        print("  1. Fast vector search (recall)")
        print("  2. Cross-encoder reranking (precision)")
        print()
        print("Usage:")
        print("  reranker.py --test    # Test reranker functionality")
        print()
        print("Or import in Python:")
        print("  from reranker import rerank_results")
        print("  results = rerank_results(query, candidates, top_k=10)")
        print()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Vector Semantic Search for Knowledge Base
Requires: pip install sentence-transformers numpy

Usage:
    python vector-search.py "how to handle authentication"
"""

import sys
import os
import json
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    print("❌ Error: Required packages not installed")
    print("Install with: pip install sentence-transformers numpy")
    sys.exit(1)

MEMORY_DIR = Path(os.environ.get("PROJECT_MEMORY_DIR", ".project-memory"))
VECTOR_DIR = MEMORY_DIR / "knowledge" / "vectors"
MODEL_NAME = "BAAI/bge-large-en-v1.5"  # Best for semantic search


def init_model():
    """Initialize the BGE embedding model"""
    print(f"Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
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


def search_semantic(query, threshold=0.7):
    """Search knowledge base using semantic similarity"""
    if not VECTOR_DIR.exists():
        print("❌ No embeddings found. Run with --generate first")
        return

    model = init_model()
    query_embedding = model.encode(query)

    print(f"\n🔍 Searching for: \"{query}\"")
    print(f"Similarity threshold: {threshold}\n")
    print("=" * 60)

    results = []

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
                    }
                )

    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    if not results:
        print("No matches found above threshold.")
        print(f"\nTry:")
        print(f"  • Lower threshold: --threshold 0.6")
        print(f"  • Different query terms")
        return

    # Display results
    for i, result in enumerate(results[:10], 1):  # Top 10
        icon = {"patterns": "✓", "failures": "⚠️", "decisions": "🤔", "gotchas": "💡"}
        print(f"\n{i}. {icon.get(result['type'], '•')} {result['type'].upper()}")
        print(f"   Similarity: {result['similarity']:.3f}")
        print(f"   {result['header']}")
        print(f"   {'-' * 60}")
        # Show first 200 chars of content
        preview = result["content"][:200].replace("\n", " ")
        print(f"   {preview}...")

    print(f"\n{'-' * 60}")
    print(f"Found {len(results)} relevant matches")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} --generate          # Generate embeddings")
        print(f"  {sys.argv[0]} \"search query\"      # Semantic search")
        print(f"  {sys.argv[0]} \"query\" --threshold 0.6  # Custom threshold")
        sys.exit(1)

    if sys.argv[1] == "--generate":
        generate_embeddings()
    else:
        query = sys.argv[1]
        threshold = 0.7

        if "--threshold" in sys.argv:
            idx = sys.argv.index("--threshold")
            threshold = float(sys.argv[idx + 1])

        search_semantic(query, threshold)


if __name__ == "__main__":
    main()

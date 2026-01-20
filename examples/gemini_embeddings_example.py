"""Example: Text Embeddings with Gemini

Demonstrates how to generate text embeddings using Google's Gemini models
through the Rhesis SDK.
"""

from pathlib import Path
from typing import List

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Make sure environment variables are set manually.")

from rhesis.sdk.models import get_model

print("=" * 60)
print("Gemini Text Embeddings Examples")
print("=" * 60)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute the cosine similarity between two vectors."""
    dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
    magnitude1 = sum(v1 * v1 for v1 in vec1) ** 0.5
    magnitude2 = sum(v2 * v2 for v2 in vec2) ** 0.5
    if not magnitude1 or not magnitude2:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


# Example 1: Basic Text Embedding
print("\n" + "-" * 60)
print("Example 1: Single Text Embedding")
print("-" * 60)

try:
    model = get_model("gemini", "text-embedding-004")
    print(f"✅ Using model: {model.model_name}")

    text = "The quick brown fox jumps over the lazy dog."

    # Generate embedding
    embedding = model.embed(text)
    print(f"✅ Generated embedding with {len(embedding)} dimensions")
    print(f"   First 5 values: {embedding[:5]}")

except ValueError as e:
    print(f"❌ Failed: {e}")
    print("   Make sure GEMINI_API_KEY is set in your .env file")


# Example 2: Batch Embeddings
print("\n" + "-" * 60)
print("Example 2: Batch Embeddings")
print("-" * 60)

try:
    model = get_model("gemini", "text-embedding-004")
    print(f"✅ Using model: {model.model_name}")

    texts = [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with multiple layers.",
        "The weather today is sunny and warm.",
    ]

    # Generate embeddings for all texts
    embeddings = model.embed(texts)
    print(f"✅ Generated {len(embeddings)} embeddings")
    for i, emb in enumerate(embeddings):
        print(f"   Text {i+1}: {len(emb)} dimensions, first 3 values: {emb[:3]}")

except ValueError as e:
    print(f"❌ Failed: {e}")
    print("   Make sure GEMINI_API_KEY is set in your .env file")


# Example 3: Semantic Similarity
print("\n" + "-" * 60)
print("Example 3: Computing Semantic Similarity")
print("-" * 60)

try:
    model = get_model("gemini", "text-embedding-004")
    print(f"✅ Using model: {model.model_name}")

    # Compare semantically similar and dissimilar texts
    text1 = "Python is a programming language."
    text2 = "Python is used for software development."
    text3 = "The cat sat on the mat."

    embeddings = model.embed([text1, text2, text3])

    sim_1_2 = cosine_similarity(embeddings[0], embeddings[1])
    sim_1_3 = cosine_similarity(embeddings[0], embeddings[2])

    print(f"\n   Text 1: '{text1}'")
    print(f"   Text 2: '{text2}'")
    print(f"   Text 3: '{text3}'")
    print(f"\n   Similarity between Text 1 and 2: {sim_1_2:.4f}")
    print(f"   Similarity between Text 1 and 3: {sim_1_3:.4f}")
    print(
        f"\n   ✅ Text 1 and 2 are {'more' if sim_1_2 > sim_1_3 else 'less'} similar "
        f"than Text 1 and 3 (as expected)"
    )

except ValueError as e:
    print(f"❌ Failed: {e}")
    print("   Make sure GEMINI_API_KEY is set in your .env file")


# Example 4: Task-specific Embeddings
print("\n" + "-" * 60)
print("Example 4: Task-specific Embeddings (Query vs Document)")
print("-" * 60)

try:
    model = get_model("gemini", "text-embedding-004")
    print(f"✅ Using model: {model.model_name}")

    # Simulate a search scenario
    query = "What is machine learning?"
    documents = [
        "Machine learning is a method of data analysis that automates analytical model building.",
        "Deep learning is a subset of machine learning based on artificial neural networks.",
        "The weather forecast predicts rain tomorrow.",
    ]

    # Embed query with task type
    query_embedding = model.embed(query, task_type="RETRIEVAL_QUERY")
    print(f"✅ Query embedding: {len(query_embedding)} dimensions")

    # Embed documents with task type
    doc_embeddings = model.embed(documents, task_type="RETRIEVAL_DOCUMENT")
    print(f"✅ Document embeddings: {len(doc_embeddings)} documents")

    # Find most relevant document
    similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in doc_embeddings]

    print(f"\n   Query: '{query}'")
    print("\n   Document similarities:")
    for i, (doc, sim) in enumerate(zip(documents, similarities)):
        print(f"   [{i+1}] Similarity: {sim:.4f} - '{doc[:60]}...'")

    best_match = similarities.index(max(similarities))
    print(f"\n   ✅ Most relevant document: Document {best_match + 1}")

except ValueError as e:
    print(f"❌ Failed: {e}")
    print("   Make sure GEMINI_API_KEY is set in your .env file")
    print("   Note: task_type parameter may not be supported by all Gemini embedding models")


# Example 5: Custom Dimensions (if supported)
print("\n" + "-" * 60)
print("Example 5: Custom Output Dimensions")
print("-" * 60)

try:
    model = get_model("gemini", "text-embedding-004")
    print(f"✅ Using model: {model.model_name}")

    text = "Testing custom dimensions for embeddings."

    # Try different dimension sizes (if supported by the model)
    for dims in [256, 512]:
        try:
            embedding = model.embed(text, output_dimensionality=dims)
            print(f"✅ Embedding with {dims} dimensions: {embedding[:3]}...")
        except Exception as e:
            print(f"⚠️  {dims} dimensions not supported: {str(e)[:80]}")

except ValueError as e:
    print(f"❌ Failed: {e}")
    print("   Make sure GEMINI_API_KEY is set in your .env file")


print("\n" + "=" * 60)
print("✅ Gemini embeddings examples complete!")
print("=" * 60)


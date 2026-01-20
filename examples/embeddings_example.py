"""Example: Text Embeddings with the SDK

Demonstrates how to generate text embeddings using different providers.
"""

from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed.")

from rhesis.sdk.models import get_model

print("=" * 60)
print("Text Embeddings Examples")
print("=" * 60)

# Example 1: Single text embedding with OpenAI
print("\n" + "-" * 60)
print("Example 1: Single text embedding")
print("-" * 60)

try:
    model = get_model("openai", "text-embedding-3-small")
    print(f"Using model: {model.model_name}")

    text = "Hello, how are you doing today?"
    embedding = model.embed(text)

    print(f"\nText: {text}")
    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

except Exception as e:
    print(f"⚠️  OpenAI embedding failed: {e}")
    print("   Make sure OPENAI_API_KEY is set in your .env file")

# Example 2: Batch embeddings
print("\n" + "-" * 60)
print("Example 2: Batch embeddings")
print("-" * 60)

try:
    model = get_model("openai", "text-embedding-3-small")

    texts = [
        "The weather is nice today.",
        "I love programming in Python.",
        "Machine learning is fascinating.",
    ]

    embeddings = model.embed(texts)

    print(f"Embedded {len(texts)} texts")
    for i, (text, emb) in enumerate(zip(texts, embeddings), 1):
        print(f"{i}. {text[:40]}... → {len(emb)} dimensions")

except Exception as e:
    print(f"⚠️  Batch embedding failed: {e}")

# Example 3: Custom dimensions
print("\n" + "-" * 60)
print("Example 3: Custom output dimensions")
print("-" * 60)

try:
    model = get_model("openai", "text-embedding-3-small")

    text = "This is a test sentence for embedding."

    # Generate embeddings with different dimensions
    for dims in [256, 512, 1024]:
        embedding = model.embed(text, dimensions=dims)
        print(f"Dimensions: {dims:4d} → Actual: {len(embedding):4d}")

except Exception as e:
    print(f"⚠️  Custom dimensions failed: {e}")

# Example 4: Input type specification
print("\n" + "-" * 60)
print("Example 4: Specify input type (query vs document)")
print("-" * 60)

try:
    model = get_model("openai", "text-embedding-3-small")

    query = "What is machine learning?"
    document = (
        "Machine learning is a subset of artificial intelligence that enables "
        "systems to learn and improve from experience without being explicitly programmed."
    )

    query_embedding = model.embed(query, input_type="query")
    doc_embedding = model.embed(document, input_type="document")

    print(f"Query embedding: {len(query_embedding)} dimensions")
    print(f"Document embedding: {len(doc_embedding)} dimensions")

except Exception as e:
    print(f"⚠️  Input type specification failed: {e}")

# Example 5: Vertex AI embeddings with task_type
print("\n" + "-" * 60)
print("Example 5: Vertex AI embeddings with task_type")
print("-" * 60)

try:
    model = get_model("vertex_ai", "textembedding-gecko")
    print(f"Using model: {model.model_name}")

    # Embedding for search/retrieval
    query = "How do I reset my password?"
    query_embedding = model.embed(query, task_type="RETRIEVAL_QUERY")

    document = "To reset your password, click on the 'Forgot Password' link on the login page."
    doc_embedding = model.embed(document, task_type="RETRIEVAL_DOCUMENT")

    print(f"\nQuery: {query}")
    print(f"Query embedding: {len(query_embedding)} dimensions")
    print(f"\nDocument: {document[:50]}...")
    print(f"Document embedding: {len(doc_embedding)} dimensions")

except Exception as e:
    print(f"⚠️  Vertex AI embedding failed: {e}")
    print("   Make sure Google Cloud credentials are configured")

# Example 6: Computing similarity
print("\n" + "-" * 60)
print("Example 6: Computing similarity between embeddings")
print("-" * 60)

try:
    import numpy as np

    model = get_model("openai", "text-embedding-3-small")

    # Embed three sentences
    sentences = [
        "The cat sat on the mat.",
        "A feline rested on the rug.",
        "The weather is sunny today.",
    ]

    embeddings = model.embed(sentences)

    # Convert to numpy arrays
    emb_arrays = [np.array(emb) for emb in embeddings]

    # Compute cosine similarities
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    print("\nSimilarity matrix:")
    print(f"{'':25s}", end="")
    for i, sent in enumerate(sentences):
        print(f"Sent {i + 1:2d}", end="  ")
    print()

    for i, sent1 in enumerate(sentences):
        print(f"{sent1[:23]:23s}  ", end="")
        for j, sent2 in enumerate(sentences):
            similarity = cosine_similarity(emb_arrays[i], emb_arrays[j])
            print(f"{similarity:.3f}  ", end="")
        print()

    print("\nNote: Sentences 1 and 2 should have high similarity (similar meaning)")
    print("      Sentence 3 should have low similarity to 1 and 2 (different topic)")

except ImportError:
    print("⚠️  NumPy not installed. Install with: pip install numpy")
except Exception as e:
    print(f"⚠️  Similarity computation failed: {e}")

print("\n" + "=" * 60)
print("✅ Embeddings examples complete!")
print("=" * 60)

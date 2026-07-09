"""
Haystack Auto-Instrumentation Example

Demonstrates zero-config observability for Haystack pipelines.
Import, call auto_instrument("haystack"), run the pipeline — done.

Prerequisites:
    1. Start the backend: docker compose up -d
    2. Set environment variables:
       export RHESIS_API_KEY=your-api-key
       export RHESIS_PROJECT_ID=your-project-id
       export GOOGLE_API_KEY=your-gemini-api-key

Run with:
    uv run --extra haystack haystack_example.py
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient
from rhesis.sdk.telemetry import auto_instrument

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

client = RhesisClient.from_environment()

print("\nEnabling Haystack auto-instrumentation...")
instrumented = auto_instrument("haystack")
print(f"Auto-instrumented frameworks: {instrumented}\n")


def example_simple_pipeline():
    """Run a minimal Haystack pipeline — spans are captured automatically."""
    from haystack import Pipeline
    from haystack.components.builders import PromptBuilder
    from haystack.components.generators import OpenAIGenerator
    from haystack.utils import Secret

    prompt = PromptBuilder(template="Answer briefly: {{ query }}")
    generator = OpenAIGenerator(
        api_key=Secret.from_env_var("OPENAI_API_KEY", strict=False) or Secret.from_token("sk-test"),
        model="gpt-4o-mini",
    )

    pipeline = Pipeline()
    pipeline.add_component("prompt", prompt)
    pipeline.add_component("generator", generator)
    pipeline.connect("prompt.prompt", "generator.prompt")

    print("Running Haystack pipeline...")
    result = pipeline.run({"prompt": {"query": "What is retrieval-augmented generation?"}})
    print(f"Pipeline output keys: {list(result.keys())}")
    return result


def example_multi_component_pipeline():
    """Demonstrate nested component inputs on a RAG-style pipeline shape."""
    from haystack import Pipeline
    from haystack.components.builders import PromptBuilder
    from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
    from haystack.document_stores.in_memory import InMemoryDocumentStore
    from haystack.dataclasses import Document

    store = InMemoryDocumentStore()
    store.write_documents(
        [
            Document(content="Haystack is an open-source LLM framework."),
            Document(content="RAG combines retrieval with generation."),
        ]
    )

    retriever = InMemoryBM25Retriever(document_store=store)
    prompt = PromptBuilder(template="Context: {% for doc in documents %}{{ doc.content }} {% endfor %}\nQ: {{ question }}")

    pipeline = Pipeline()
    pipeline.add_component("retriever", retriever)
    pipeline.add_component("prompt", prompt)
    pipeline.connect("retriever.documents", "prompt.documents")

    print("Running multi-component pipeline...")
    result = pipeline.run(
        {
            "retriever": {"query": "What is Haystack?"},
            "prompt": {"question": "What is Haystack?"},
        }
    )
    print(f"Multi-component output keys: {list(result.keys())}")
    return result


def main():
    print("=" * 70)
    print("Rhesis Telemetry - Haystack Auto-Instrumentation")
    print("=" * 70)

    try:
        example_simple_pipeline()
        time.sleep(1)
        example_multi_component_pipeline()
        print("\nCheck your Rhesis dashboard for ai.* spans:")
        print("  - ai.agent.invoke for pipeline runs")
        print("  - ai.llm.invoke / ai.retrieval / ai.transform for components")
    except Exception as exc:
        print(f"\nExample failed: {exc}")
        print("Install extras with: uv run --extra haystack haystack_example.py")
        raise


if __name__ == "__main__":
    main()

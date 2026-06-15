"""
LlamaIndex RAG Telemetry Example

Demonstrates manual Rhesis instrumentation for a LlamaIndex retrieve-and-synthesize
workflow:
  - Retrieval span (ai.retrieval) via @observe on the retriever step
  - LLM synthesis span (ai.llm.invoke) via @observe on response generation
  - Pipeline boundary (ai.agent.invoke) via @observe on the RAG entrypoint

Note: LlamaIndex supports OpenTelemetry / OpenInference, but this example uses
explicit @observe wrappers so retrieval and synthesis boundaries are visible in
Rhesis today. Full framework auto-instrumentation is tracked in #1083.

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       plus OPENAI_API_KEY or GOOGLE_API_KEY (see LLAMAINDEX_PROVIDER)

Run with:
    cd examples/telemetry
    uv run --extra llamaindex llamaindex_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from llama_index.core import Document, Settings, VectorStoreIndex, get_response_synthesizer
from llama_index.core.schema import NodeWithScore
from opentelemetry import trace

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry import auto_instrument
from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents, create_llm_attributes
from rhesis.telemetry.schemas import AIOperationType

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

print("\n🔧 Calling auto_instrument() (LangChain/LangGraph if installed)...")
instrumented = auto_instrument()
print(f"✅ Auto-instrumented: {instrumented or '(none — LlamaIndex not yet covered)'}\n")
print("📋 Retrieval + synthesis use @observe in this example.")
print("   Native LlamaIndex auto_instrument(): https://github.com/rhesis-ai/rhesis/issues/1083\n")

Provider = Literal["openai", "gemini"]
TOP_K = 3

SAMPLE_DOCS = [
    Document(
        text=(
            "RAG pipelines combine retrieval with generation. Observability on the "
            "retrieval step shows which chunks influenced the answer."
        )
    ),
    Document(
        text=(
            "Embedding and LLM calls inside LlamaIndex should appear as child spans "
            "once native SDK instrumentation lands in Rhesis."
        )
    ),
    Document(
        text=(
            "Multi-step agent workflows benefit from nested traces: pipeline, "
            "retrieval, then synthesis."
        )
    ),
]


def resolve_provider() -> Provider:
    raw = os.getenv("LLAMAINDEX_PROVIDER", "openai").strip().lower()
    if raw in ("google", "gemini"):
        return "gemini"
    if raw != "openai":
        raise ValueError(f"LLAMAINDEX_PROVIDER must be 'openai' or 'gemini', got {raw!r}")
    return "openai"


def configure_llamaindex_settings(provider: Provider) -> tuple[str, str]:
    """Configure global LlamaIndex LLM and embedding from environment."""
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required when LLAMAINDEX_PROVIDER=openai")
        from llama_index.embeddings.openai import OpenAIEmbedding
        from llama_index.llms.openai import OpenAI

        model = os.getenv("LLAMAINDEX_MODEL", "gpt-4o-mini")
        embed_model = os.getenv("LLAMAINDEX_EMBED_MODEL", "text-embedding-3-small")
        Settings.llm = OpenAI(model=model, api_key=os.environ["OPENAI_API_KEY"])
        Settings.embed_model = OpenAIEmbedding(
            model=embed_model,
            api_key=os.environ["OPENAI_API_KEY"],
        )
        return "openai", model

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is required when LLAMAINDEX_PROVIDER=gemini"
        )
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
    from llama_index.llms.google_genai import GoogleGenAI

    model = os.getenv("LLAMAINDEX_MODEL", "gemini-2.0-flash")
    embed_model = os.getenv("LLAMAINDEX_EMBED_MODEL", "text-embedding-004")
    Settings.llm = GoogleGenAI(model=model, api_key=api_key)
    Settings.embed_model = GoogleGenAIEmbedding(model_name=embed_model, api_key=api_key)
    return "google", model


def build_index() -> VectorStoreIndex:
    """In-memory vector index over sample documents (embedding calls run here)."""
    return VectorStoreIndex.from_documents(SAMPLE_DOCS)


@observe(
    span_name=AIOperationType.RETRIEVAL,
    **{
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL,
        AIAttributes.RETRIEVAL_BACKEND: "llamaindex",
        AIAttributes.RETRIEVAL_TOP_K: TOP_K,
    },
)
def retrieve_nodes(index: VectorStoreIndex, question: str) -> list[NodeWithScore]:
    """Retrieve top-k nodes for the question."""
    retriever = index.as_retriever(similarity_top_k=TOP_K)
    nodes = retriever.retrieve(question)
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(AIEvents.RETRIEVAL_QUERY, question[:500])
        span.set_attribute("retrieval.node_count", len(nodes))
    return nodes


@observe(
    span_name=AIOperationType.LLM_INVOKE,
    **create_llm_attributes(provider="llamaindex", model_name="synthesis"),
)
def synthesize_answer(question: str, nodes: list[NodeWithScore]) -> str:
    """Generate a final answer from retrieved nodes."""
    synthesizer = get_response_synthesizer()
    response = synthesizer.synthesize(question, nodes=nodes)
    text = str(response)
    span = trace.get_current_span()
    if span.is_recording():
        llm = Settings.llm
        span.set_attribute(AIAttributes.MODEL_PROVIDER, type(llm).__name__)
        model = getattr(llm, "model", None)
        if model is not None:
            span.set_attribute(AIAttributes.MODEL_NAME, str(model))
    return text


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "llamaindex_rag_pipeline"},
)
def run_rag_pipeline(index: VectorStoreIndex, question: str) -> str:
    """
    Retrieve context then synthesize an answer.

    Trace hierarchy:
      llamaindex_rag_pipeline (ai.agent.invoke)
        ├─ ai.retrieval (chunk lookup)
        └─ ai.llm.invoke (answer synthesis)
    """
    nodes = retrieve_nodes(index, question)
    return synthesize_answer(question, nodes)


def main() -> None:
    provider = resolve_provider()
    llm_provider, model_name = configure_llamaindex_settings(provider)

    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - LlamaIndex RAG Example")
    print("=" * 70)
    print("\nWorkflow: build index → retrieve → synthesize")
    print("Tracing:")
    print("  • @observe — ai.agent.invoke on llamaindex_rag_pipeline")
    print("  • @observe — ai.retrieval on chunk retrieval")
    print("  • @observe — ai.llm.invoke on synthesis")
    print("  • auto_instrument() — future native LlamaIndex support (#1083)")
    print(f"\nProvider: {provider} ({llm_provider})")
    print(f"Model: {model_name}")
    print("=" * 70 + "\n")

    print("📚 Building in-memory index...")
    index = build_index()

    question = "Why is observability important for RAG applications?"
    print(f"📍 Question: {question}\n")

    answer = run_rag_pipeline(index, question)

    print("\n" + "=" * 70)
    print("✅ RAG pipeline complete!")
    print("=" * 70)
    print(f"\nAnswer:\n{answer}\n")
    print("📊 View traces: http://localhost:3000/traces")
    print("   Look for: pipeline → retrieval → llm.invoke")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

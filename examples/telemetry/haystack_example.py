"""
Haystack Auto-Instrumentation Example

Zero-config observability for Haystack pipelines and agents. Haystack does not emit
OpenTelemetry spans on its own -- it has its own tracing abstraction -- so this integration
registers a tracer with it and writes Rhesis ai.* spans as the spans are opened:
  - Pipeline runs (function.haystack.pipeline.run) as the trace root
  - Every component run, named after what it does: ai.llm.invoke for generators,
    ai.retrieval for retrievers, ai.embedding.generate for embedders
  - Agent runs (ai.agent.invoke), per-step LLM calls, and per-call tool spans (ai.tool.invoke)
  - Model name and token usage on LLM spans, prompts and completions as span events
  - Conversation grouping across turns via RhesisTracing

IMPORTANT: HAYSTACK_CONTENT_TRACING_ENABLED must be set to "true" BEFORE haystack is imported.
Haystack reads it once at import time, so setting it later has no effect and spans carry no
prompts or completions. This file sets it at the top for that reason.

Prerequisites:
    1. Start the backend: ./rh dev up   (run ./rh dev status for this checkout's ports)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID and OPENAI_API_KEY

Run with:
    cd examples/telemetry
    uv run --extra haystack haystack_example.py

Traces appear in the Rhesis UI under Traces.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Must precede every haystack import. Set it in your own app's entry point the same way, or export
# it in the environment that starts the process.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

from haystack import Document, Pipeline  # noqa: E402
from haystack.components.agents import Agent  # noqa: E402
from haystack.components.builders import ChatPromptBuilder  # noqa: E402
from haystack.components.generators.chat import OpenAIChatGenerator  # noqa: E402
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever  # noqa: E402
from haystack.dataclasses import ChatMessage  # noqa: E402
from haystack.document_stores.in_memory import InMemoryDocumentStore  # noqa: E402
from haystack.tools import Tool  # noqa: E402

from rhesis.sdk import RhesisClient  # noqa: E402
from rhesis.sdk.telemetry import auto_instrument  # noqa: E402
from rhesis.sdk.telemetry.integrations.haystack import (  # noqa: E402
    RhesisTracing,
    rhesis_invocation_context,
)

# To show a "view this trace" link in your own app, call get_trace_url() from *inside* a run --
# from a component, or from the function that invoked the pipeline. It reads the trace currently
# open in this context, so outside a run it is empty:
#
#     from rhesis.sdk.telemetry.integrations.haystack import get_trace_id, get_trace_url

MODEL = os.getenv("HAYSTACK_MODEL", "gpt-4o-mini")

# The client installs the tracer provider, so it has to come first. auto_instrument returns an
# empty list if it does not.
RhesisClient.from_environment()

print("\n🔧 Enabling Haystack auto-instrumentation...")
instrumented = auto_instrument("haystack")
print(f"✅ Auto-instrumented frameworks: {instrumented}\n")
if not instrumented:
    raise SystemExit(
        "Haystack was not instrumented. Is haystack-ai installed and RHESIS_API_KEY set?"
    )


def build_rag_pipeline() -> Pipeline:
    """A retriever-into-prompt-into-generator pipeline, the common RAG shape."""
    store = InMemoryDocumentStore()
    store.write_documents(
        [
            Document(content="Rhesis is a testing and validation platform for LLM applications."),
            Document(content="Haystack is an open-source framework for building LLM pipelines."),
            Document(content="Penelope drives multi-turn conversation tests against a target."),
        ]
    )

    template = [
        ChatMessage.from_user(
            "Answer using only the context below.\n\n"
            "{% for doc in documents %}{{ doc.content }}\n{% endfor %}\n"
            "Question: {{ question }}"
        )
    ]

    pipe = Pipeline()
    pipe.add_component("retriever", InMemoryBM25Retriever(document_store=store))
    pipe.add_component(
        "prompt", ChatPromptBuilder(template=template, required_variables=["question"])
    )
    pipe.add_component("llm", OpenAIChatGenerator(model=MODEL))
    pipe.connect("retriever.documents", "prompt.documents")
    pipe.connect("prompt.prompt", "llm.messages")
    return pipe


def build_agent() -> Agent:
    """An agent with one tool, so the trace shows a tool span under the agent."""

    def get_weather(city: str) -> str:
        return f"It is 18C and sunny in {city}."

    weather = Tool(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        function=get_weather,
    )
    agent = Agent(
        chat_generator=OpenAIChatGenerator(model=MODEL),
        tools=[weather],
        system_prompt="You are a concise weather assistant. Use the tool when asked about weather.",
    )
    agent.warm_up()
    return agent


# ---------------------------------------------------------------------------------------------
# 1. A traced pipeline run. rhesis_invocation_context attaches metadata to every span in the run,
#    so you can filter the trace by your own session or test-run id.
# ---------------------------------------------------------------------------------------------
print("=" * 70)
print("1. RAG pipeline")
print("=" * 70)

rag = build_rag_pipeline()
question = "What is Rhesis?"
with rhesis_invocation_context({"session_id": "haystack-example", "user_id": "demo-user"}):
    result = rag.run({"retriever": {"query": question}, "prompt": {"question": question}})

print(f"Q: {question}")
print(f"A: {result['llm']['replies'][0].text}\n")

# ---------------------------------------------------------------------------------------------
# 2. An agent run. The agent span is the trace root, with an LLM span per step and a tool span
#    per tool call underneath it.
# ---------------------------------------------------------------------------------------------
print("=" * 70)
print("2. Agent with a tool")
print("=" * 70)

agent = build_agent()
agent_result = agent.run(messages=[ChatMessage.from_user("What is the weather in Berlin?")])
print(f"A: {agent_result['last_message'].text}\n")

# ---------------------------------------------------------------------------------------------
# 3. A multi-turn conversation. Each turn gets its own root span, and every turn after the first
#    joins the first one's trace, so the conversation reads as one trace rather than one per
#    exchange. Assign turn.output yourself -- only your app knows which part of the result is the
#    reply the user saw.
# ---------------------------------------------------------------------------------------------
print("=" * 70)
print("3. Multi-turn conversation")
print("=" * 70)

tracing = RhesisTracing("Haystack example assistant")
tracing.start_conversation("haystack-example-conversation")

conversation_trace_id = ""
for message in ["What is Haystack?", "And what is Penelope for?"]:
    with tracing.turn(message) as turn:
        turn_result = rag.run({"retriever": {"query": message}, "prompt": {"question": message}})
        reply = turn_result["llm"]["replies"][0].text
        turn.output = reply
        conversation_trace_id = format(turn.span.get_span_context().trace_id, "032x")
    print(f"Q: {message}")
    print(f"A: {reply}\n")

tracing.flush()

print("=" * 70)
print("Done. Traces are in the Rhesis UI under Traces.")
print(f"Both turns above share trace {conversation_trace_id}")
print("=" * 70)

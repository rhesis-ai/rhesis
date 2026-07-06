"""
Pydantic AI Multi-Agent Delegation Example

Demonstrates how Rhesis traces multi-agent Pydantic AI systems. A coordinator
agent delegates work to two specialist agents by calling them inside tools -
Pydantic AI's idiomatic delegation pattern (it has no separate "handoff"
primitive).

With auto_instrument() enabled, each delegation renders in Rhesis as:
  - the coordinator's ai.agent.invoke span,
  - an ai.tool.invoke span for the delegating tool call,
  - the specialist's ai.agent.invoke span nested underneath, and
  - a synthesized ai.agent.handoff span carrying
    ai.agent.handoff.from / ai.agent.handoff.to, which is what lets the
    Rhesis Graph View draw the coordinator -> specialist edges.

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       plus OPENAI_API_KEY or GOOGLE_API_KEY (see PYDANTIC_AI_MODEL)

Run with:
    cd examples/telemetry
    uv run --extra pydantic-ai pydantic_ai_multi_agent_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

from rhesis.sdk import RhesisClient
from rhesis.sdk.telemetry import auto_instrument

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

print("\n🔧 Enabling Pydantic AI auto-instrumentation...")
instrumented_frameworks = auto_instrument()
print(f"✅ Auto-instrumented frameworks: {instrumented_frameworks}\n")

MODEL = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o-mini")

# --- Specialist agents -------------------------------------------------------

research_agent = Agent(
    MODEL,
    name="research_specialist",
    system_prompt=(
        "You are a research specialist. Answer factual questions concisely, "
        "in at most three sentences."
    ),
)

writing_agent = Agent(
    MODEL,
    name="writing_specialist",
    system_prompt=(
        "You are a writing specialist. Rewrite the given text as a single "
        "punchy paragraph for a general audience."
    ),
)

# --- Coordinator agent -------------------------------------------------------

coordinator = Agent(
    MODEL,
    name="coordinator",
    system_prompt=(
        "You coordinate specialists to answer the user. First call "
        "research_topic to gather facts, then call polish_text to rewrite "
        "them, and return the polished result."
    ),
)


@coordinator.tool
def research_topic(ctx: RunContext[None], question: str) -> str:
    """Delegate a factual question to the research specialist."""
    # Calling another agent inside a tool is Pydantic AI's delegation
    # pattern. Rhesis synthesizes an ai.agent.handoff span for this
    # transition (coordinator -> research_specialist) automatically.
    result = research_agent.run_sync(question)
    return str(result.output)


@coordinator.tool
def polish_text(ctx: RunContext[None], text: str) -> str:
    """Delegate rough text to the writing specialist for a rewrite."""
    result = writing_agent.run_sync(text)
    return str(result.output)


def main() -> None:
    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - Pydantic AI Multi-Agent Delegation")
    print("=" * 70)
    print("\nTopology: coordinator -> research_specialist, writing_specialist")
    print(f"Model: {MODEL}")
    print("=" * 70 + "\n")

    question = "Why do LLM agents need distributed tracing?"
    print(f"📍 Question: {question}\n")

    result = coordinator.run_sync(question)

    print("\n" + "=" * 70)
    print("✅ Multi-agent run complete!")
    print("=" * 70)
    print(f"\nAnswer:\n{result.output}")
    print("\n📊 View traces: http://localhost:3000/traces")
    print("\nWhat was automatically traced:")
    print("  ✓ coordinator agent run (ai.agent.invoke)")
    print("  ✓ research_topic / polish_text tool calls (ai.tool.invoke)")
    print("  ✓ research_specialist / writing_specialist runs nested under them")
    print("  ✓ ai.agent.handoff spans (from=coordinator, to=<specialist>)")
    print("  ✓ every model call along the way (ai.llm.invoke with tokens)")
    print("\n💡 The Graph View connects the agents via the handoff from/to edges.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

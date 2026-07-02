"""
Pydantic AI Auto-Instrumentation Example

This example demonstrates zero-config observability for Pydantic AI agents.
After calling auto_instrument(), every Agent.run() / run_sync() call is traced
automatically as an ai.agent.invoke span - no @observe wrappers required:
  - Agent name, model name, and provider attributes
  - Prompt and completion events (structured outputs recorded as JSON)
  - Token usage (input / output / total)
  - Errors with status and stack traces

Tool invocation spans still use @observe below; native tool and handoff spans
for Pydantic AI are tracked as a follow-up to
https://github.com/rhesis-ai/rhesis/pull/2057.

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       plus OPENAI_API_KEY or GOOGLE_API_KEY (see PYDANTIC_AI_MODEL)

Run with:
    cd examples/telemetry
    uv run --extra pydantic-ai pydantic_ai_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from rhesis.telemetry.schemas import AIOperationType

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry import auto_instrument
from rhesis.sdk.telemetry.attributes import create_tool_attributes

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

# Enable auto-instrumentation for Pydantic AI
# Every Agent.run() / run_sync() call is traced automatically from here on!
print("\n🔧 Enabling Pydantic AI auto-instrumentation...")
instrumented_frameworks = auto_instrument()
print(f"✅ Auto-instrumented frameworks: {instrumented_frameworks}\n")


class ObservabilityBrief(BaseModel):
    """Structured output the agent must return."""

    title: str = Field(description="Short title for the topic")
    bullets: list[str] = Field(
        min_length=2,
        max_length=4,
        description="Concrete bullet points about observability",
    )
    tool_snippet_used: bool = Field(
        description="Whether the lookup_observability_snippet tool was used"
    )


def resolve_model() -> str:
    """Resolve LiteLLM-style model id from PYDANTIC_AI_MODEL and API keys in .env."""
    model = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o-mini")
    model_lower = model.lower()

    if model_lower.startswith("openai:") or "gpt" in model_lower:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(f"OPENAI_API_KEY is required for model {model!r}")
    elif model_lower.startswith("google") or "gemini" in model_lower:
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            raise ValueError(f"GOOGLE_API_KEY (or GEMINI_API_KEY) is required for model {model!r}")
    elif model_lower.startswith("anthropic:") or "claude" in model_lower:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(f"ANTHROPIC_API_KEY is required for model {model!r}")

    return model


def build_agent(model: str) -> Agent[None, ObservabilityBrief]:
    """Create a Pydantic AI agent with structured output and one optional tool."""
    return Agent(
        model,
        name="topic_analyst",
        output_type=ObservabilityBrief,
        system_prompt=(
            "You explain why observability matters for LLM applications. "
            "Call lookup_observability_snippet when you need a concrete fact, "
            "then return structured bullets. Set tool_snippet_used accordingly."
        ),
    )


@observe(
    span_name=AIOperationType.TOOL_INVOKE,
    **create_tool_attributes(
        tool_name="lookup_observability_snippet",
        tool_type="function",
    ),
)
def _lookup_observability_snippet(topic: str) -> str:
    """Return a canned observability fact (simulates a retrieval/tool backend)."""
    snippets = {
        "latency": "P95 latency per agent step helps isolate slow handoffs in multi-agent flows.",
        "cost": "Token and cost attributes per model call make regressions visible before release.",
        "debugging": "Trace hierarchies show which agent or tool produced an unexpected answer.",
    }
    key = next((k for k in snippets if k in topic.lower()), "debugging")
    return snippets[key]


def register_tools(agent: Agent[None, ObservabilityBrief]) -> None:
    """Register tools on the agent; implementations use @observe for tool spans."""

    @agent.tool
    def lookup_observability_snippet(ctx: RunContext[None], topic: str) -> str:
        """Fetch a short observability fact for the given topic."""
        return _lookup_observability_snippet(topic)


def main() -> None:
    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - Pydantic AI Auto-Instrumentation")
    print("=" * 70)
    print("\nThis example demonstrates ZERO-CONFIG observability for Pydantic AI.")
    print("Agent runs are traced automatically - no @observe wrappers needed.")
    model_name = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o-mini")
    print(f"\nModel: {model_name}")
    print("=" * 70 + "\n")

    topic = "debugging multi-agent LLM latency regressions"
    print(f"📍 Topic: {topic}\n")

    model = resolve_model()
    agent = build_agent(model)
    register_tools(agent)
    prompt = (
        f"Explain why observability matters when shipping LLM apps about: {topic}. "
        "Use the lookup_observability_snippet tool once, then return structured output."
    )

    # This call is traced automatically as ai.agent.invoke - no wrapper needed!
    result = agent.run_sync(prompt)
    brief = result.output

    print("\n" + "=" * 70)
    print("✅ Agent run complete!")
    print("=" * 70)
    print(f"\nTitle: {brief.title}")
    print("Bullets:")
    for bullet in brief.bullets:
        print(f"  • {bullet}")
    print(f"\nTool snippet used: {brief.tool_snippet_used}")
    print("\n📊 View traces: http://localhost:3000/traces")
    print("\nWhat was automatically traced:")
    print("  ✓ Agent run (ai.agent.invoke with agent name, model, provider)")
    print("  ✓ Prompt and completion events (structured output as JSON)")
    print("  ✓ Token usage (input / output / total)")
    print("\n💡 Key Benefits:")
    print("   • Zero code changes needed (just call auto_instrument())")
    print("   • Works with both run() and run_sync()")
    print("   • Structured outputs keep their shape (model_dump_json)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

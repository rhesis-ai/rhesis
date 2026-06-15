"""
Pydantic AI Telemetry Example

Demonstrates manual Rhesis instrumentation for Pydantic AI agents:
  - Agent run span (ai.agent.invoke) via @observe
  - Tool invocation span (ai.tool.invoke) via @observe on registered tools
  - Structured output (Pydantic model) from agent.run_sync()
  - Nested trace hierarchy under pydantic_ai_observability_pipeline

Note: Pydantic AI supports OpenTelemetry / OpenInference, but this example uses
explicit @observe wrappers so agent and tool boundaries are visible in Rhesis today.
Per-step LLM spans via auto_instrument() are tracked in #1083.

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

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry.attributes import AIAttributes, create_tool_attributes
from rhesis.telemetry.schemas import AIOperationType

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

print("\n📋 Pydantic AI example uses manual @observe instrumentation.")
print("   Agent runs and tools are traced explicitly; native auto_instrument()")
print("   for Pydantic AI is planned in https://github.com/rhesis-ai/rhesis/issues/1083\n")


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
            raise ValueError(
                f"GOOGLE_API_KEY (or GEMINI_API_KEY) is required for model {model!r}"
            )
    elif model_lower.startswith("anthropic:") or "claude" in model_lower:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(f"ANTHROPIC_API_KEY is required for model {model!r}")

    return model


def build_agent(model: str) -> Agent[None, ObservabilityBrief]:
    """Create a Pydantic AI agent with structured output and one optional tool."""
    return Agent(
        model,
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
def lookup_observability_snippet(topic: str) -> str:
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
    def lookup_observability_snippet_tool(
        ctx: RunContext[None], topic: str
    ) -> str:
        """Fetch a short observability fact for the given topic."""
        return lookup_observability_snippet(topic)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "topic_analyst"},
)
def run_topic_analyst(agent: Agent[None, ObservabilityBrief], prompt: str) -> ObservabilityBrief:
    """Run the Pydantic AI agent (includes internal model calls inside this span)."""
    result = agent.run_sync(prompt)
    return result.output


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "pydantic_ai_observability_pipeline"},
)
def run_observability_pipeline(topic: str) -> ObservabilityBrief:
    """
    End-to-end pipeline with nested spans in Rhesis.

    Trace hierarchy:
      pydantic_ai_observability_pipeline
        └─ topic_analyst (ai.agent.invoke)
             ├─ lookup_observability_snippet (ai.tool.invoke), if the model calls it
             └─ internal LLM steps (visible via future OTel / #1083 auto-instrumentation)
    """
    model = resolve_model()
    agent = build_agent(model)
    register_tools(agent)
    prompt = (
        f"Explain why observability matters when shipping LLM apps about: {topic}. "
        "Use the lookup_observability_snippet tool once, then return structured output."
    )
    return run_topic_analyst(agent, prompt)


def main() -> None:
    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - Pydantic AI Example")
    print("=" * 70)
    print("\nInstrumentation: manual @observe (agent run + tool)")
    print("Structured output: ObservabilityBrief (Pydantic model)")
    model_name = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o-mini")
    print(f"\nModel: {model_name}")
    print("=" * 70 + "\n")

    topic = "debugging multi-agent LLM latency regressions"
    print(f"📍 Topic: {topic}\n")

    brief = run_observability_pipeline(topic)

    print("\n" + "=" * 70)
    print("✅ Agent run complete!")
    print("=" * 70)
    print(f"\nTitle: {brief.title}")
    print("Bullets:")
    for bullet in brief.bullets:
        print(f"  • {bullet}")
    print(f"\nTool snippet used: {brief.tool_snippet_used}")
    print("\n📊 View traces: http://localhost:3000/traces")
    print("   Look for: pipeline → topic_analyst → tool (if called)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

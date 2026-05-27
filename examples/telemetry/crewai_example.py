"""
CrewAI Multi-Agent Telemetry Example

Demonstrates Rhesis observability for CrewAI orchestration workflows:
  - Multiple agents (planner, researcher, writer)
  - Task delegation and sequential orchestration
  - Nested trace hierarchy (pipeline → agents → LLM calls)
  - Agent-to-agent handoff visibility (ai.agent.handoff spans)
  - Automatic LLM telemetry via auto_instrument()

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       plus OPENAI_API_KEY or GOOGLE_API_KEY (see CREWAI_MODEL)

Run with:
    cd examples/telemetry
    uv run --extra crewai crewai_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

import os
from pathlib import Path

from crewai import Agent, LLM, Task
from dotenv import load_dotenv

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry import auto_instrument
from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import AIOperationType

os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize telemetry export to Rhesis
RhesisClient.from_environment()

print("\n🔧 Enabling auto_instrument() for installed AI frameworks...")
instrumented = auto_instrument()
print(f"✅ Auto-instrumented: {instrumented or '(none detected)'}\n")


def build_llm() -> LLM:
    """Build CrewAI LLM from CREWAI_MODEL and provider API keys in .env."""
    model = os.getenv("CREWAI_MODEL", "gemini/gemini-2.0-flash")
    temperature = float(os.getenv("CREWAI_TEMPERATURE", "0.7"))
    model_lower = model.lower()

    api_key: str | None = None
    if "gemini" in model_lower or model_lower.startswith("google/"):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                f"GOOGLE_API_KEY (or GEMINI_API_KEY) is required for model {model!r}"
            )
    elif "gpt" in model_lower or "openai" in model_lower:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(f"OPENAI_API_KEY is required for model {model!r}")
    elif "claude" in model_lower or "anthropic" in model_lower:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(f"ANTHROPIC_API_KEY is required for model {model!r}")

    kwargs: dict = {"model": model, "temperature": temperature}
    if api_key:
        kwargs["api_key"] = api_key
    return LLM(**kwargs)


def build_tasks(topic: str, llm: LLM) -> tuple[Task, Task, Task]:
    """Create planner → researcher → writer tasks with CrewAI context chaining."""
    planner = Agent(
        role="Content Planner",
        goal="Break topics into clear, actionable research steps",
        backstory=(
            "You plan multi-agent content workflows and define what each "
            "downstream agent should focus on."
        ),
        llm=llm,
        verbose=True,
    )
    researcher = Agent(
        role="Research Specialist",
        goal="Collect concrete facts that satisfy the plan",
        backstory=(
            "You execute research plans and return structured findings "
            "for writers and analysts."
        ),
        llm=llm,
        verbose=True,
    )
    writer = Agent(
        role="Technical Writer",
        goal="Turn research into concise, accurate prose",
        backstory=(
            "You produce short summaries for engineering audiences "
            "based on prior agent outputs."
        ),
        llm=llm,
        verbose=True,
    )

    planning_task = Task(
        description=(
            f"Create a 3-step research plan for this topic: {topic}. "
            "Each step must be one sentence and actionable for a research agent."
        ),
        expected_output="A numbered 3-step plan.",
        agent=planner,
    )

    research_task = Task(
        description=(
            f"Follow the plan and research: {topic}. "
            "Return exactly 3 bullet points with concrete facts."
        ),
        expected_output="Three bullet points with facts.",
        agent=researcher,
        context=[planning_task],
    )

    writing_task = Task(
        description=(
            "Using the plan and research, write a 2-sentence summary "
            "for a product/engineering audience."
        ),
        expected_output="A 2-sentence summary.",
        agent=writer,
        context=[planning_task, research_task],
    )

    return planning_task, research_task, writing_task


def _task_output(task: Task) -> str:
    """Run a CrewAI task; LLM calls are traced via auto_instrument()."""
    return str(task.execute_sync().raw)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "planner"},
)
def run_planner(planning_task: Task) -> str:
    """Planner agent: define the research plan."""
    return _task_output(planning_task)


@observe(
    span_name=AIOperationType.AGENT_HANDOFF,
    **{
        AIAttributes.AGENT_HANDOFF_FROM: "planner",
        AIAttributes.AGENT_HANDOFF_TO: "researcher",
    },
)
def handoff_planner_to_researcher(research_task: Task) -> str:
    """Handoff from planner to researcher."""
    return run_researcher(research_task)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "researcher"},
)
def run_researcher(research_task: Task) -> str:
    """Researcher agent: gather facts per the plan."""
    return _task_output(research_task)


@observe(
    span_name=AIOperationType.AGENT_HANDOFF,
    **{
        AIAttributes.AGENT_HANDOFF_FROM: "researcher",
        AIAttributes.AGENT_HANDOFF_TO: "writer",
    },
)
def handoff_researcher_to_writer(writing_task: Task) -> str:
    """Handoff from researcher to writer."""
    return run_writer(writing_task)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "writer"},
)
def run_writer(writing_task: Task) -> str:
    """Writer agent: produce the final summary."""
    return _task_output(writing_task)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "crewai_content_pipeline"},
)
def run_content_pipeline(topic: str) -> str:
    """
    Orchestrate planner → researcher → writer with explicit handoff spans.

    Trace hierarchy (nested under this root):
      crewai_content_pipeline
        ├─ planner (ai.agent.invoke) + LLM child spans
        ├─ handoff planner → researcher
        │    └─ researcher (ai.agent.invoke) + LLM child spans
        ├─ handoff researcher → writer
        │    └─ writer (ai.agent.invoke) + LLM child spans
    """
    llm = build_llm()
    planning_task, research_task, writing_task = build_tasks(topic, llm)

    run_planner(planning_task)
    handoff_planner_to_researcher(research_task)
    return handoff_researcher_to_writer(writing_task)


def main() -> None:
    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - CrewAI Multi-Agent Example")
    print("=" * 70)
    print("\nAgents: planner → researcher → writer")
    print("Tracing:")
    print("  • auto_instrument() for LLM cost, latency, and token spans")
    print("  • ai.agent.invoke per agent")
    print("  • ai.agent.handoff between agents")
    print("  • Nested hierarchy under crewai_content_pipeline")
    model_name = os.getenv("CREWAI_MODEL", "gemini/gemini-2.0-flash")
    print(f"\nLLM: {model_name}")
    print("=" * 70 + "\n")

    topic = "Why multi-agent observability matters when shipping LLM applications"
    print(f"📍 Topic: {topic}\n")

    output = run_content_pipeline(topic)

    print("\n" + "=" * 70)
    print("✅ Pipeline complete!")
    print("=" * 70)
    print(f"\nFinal output:\n{output}\n")
    print("📊 View traces: http://localhost:3000/traces")
    print("   Look for nested spans: pipeline → agents → handoffs → LLM calls")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

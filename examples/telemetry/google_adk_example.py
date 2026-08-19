"""
Google ADK Auto-Instrumentation Example

This example demonstrates zero-config observability for Google ADK agents.
After calling auto_instrument(), every span ADK already emits is translated into
the Rhesis ai.* schema - no @observe wrappers required:
  - Agent activations (ai.agent.invoke) with agent names
  - One LLM span per model call (ai.llm.invoke) with model, provider, token
    counts, and ai.prompt / ai.completion events carrying the real text
  - Tool executions (ai.tool.invoke) with ai.tool.input / ai.tool.output events
  - Agent-to-agent handoffs (ai.agent.handoff) for both of ADK's multi-agent
    mechanisms - this example uses sub_agents + transfer_to_agent
  - Conversation turn roots, so the two turns below group as one conversation

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       plus GOOGLE_API_KEY (see GOOGLE_ADK_MODEL)

Run with:
    cd examples/telemetry
    uv run --extra google-adk google_adk_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

import asyncio
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# ADK's experimental-feature notice is aimed at ADK developers and only clutters
# the output here.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature .*", category=UserWarning)

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from google.adk.agents import Agent  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402
from rhesis.telemetry.context import set_conversation_id  # noqa: E402

from rhesis.sdk import RhesisClient  # noqa: E402
from rhesis.sdk.telemetry import auto_instrument  # noqa: E402

# The client installs the tracer provider whose exporter the integration wraps,
# so it has to come first.
RhesisClient.from_environment()

print("\n🔧 Enabling Google ADK auto-instrumentation...")
instrumented_frameworks = auto_instrument("google_adk")
print(f"✅ Auto-instrumented frameworks: {instrumented_frameworks}\n")

MODEL = os.getenv("GOOGLE_ADK_MODEL", "gemini-3.1-flash-lite")
APP_NAME = "telemetry-example"
USER_ID = "example-user"
SESSION_ID = "example-session"
CONVERSATION_ID = "example-conversation"


def check_refund_policy(order_id: str) -> dict:
    """Look up the refund policy that applies to an order.

    Args:
        order_id: The customer's order identifier.
    """
    return {"order_id": order_id, "refundable": True, "window_days": 30}


def check_shipping_status(order_id: str) -> dict:
    """Look up the shipping status of an order.

    Args:
        order_id: The customer's order identifier.
    """
    return {"order_id": order_id, "status": "in transit", "eta_days": 2}


def build_support_router() -> Agent:
    """A router with two sub_agents, reached via ADK's transfer_to_agent tool."""
    billing = Agent(
        name="billing_agent",
        model=MODEL,
        description="Handles refunds, invoices and payment questions.",
        instruction="You handle billing. Use check_refund_policy when asked about refunds.",
        tools=[check_refund_policy],
    )
    shipping = Agent(
        name="shipping_agent",
        model=MODEL,
        description="Handles delivery, tracking and shipping questions.",
        instruction="You handle shipping. Use check_shipping_status for tracking questions.",
        tools=[check_shipping_status],
    )
    # Declaring sub_agents is what makes ADK expose transfer_to_agent to the
    # model, which is what produces the handoff edges in the Rhesis Graph View.
    return Agent(
        name="support_router",
        model=MODEL,
        description="Routes customer support questions to the right specialist.",
        instruction=(
            "You are a support router. Do not answer questions yourself. "
            "Transfer to billing_agent for refunds or payments, and to shipping_agent "
            "for delivery or tracking."
        ),
        sub_agents=[billing, shipping],
    )


async def ask(runner: Runner, question: str) -> str:
    """Run one turn and return the assistant's last text reply."""
    replies: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=types.Content(role="user", parts=[types.Part(text=question)]),
    ):
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", None) or ():
            if getattr(part, "text", None):
                replies.append(part.text)
    return replies[-1] if replies else "(no text reply)"


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    runner = Runner(
        agent=build_support_router(),
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Marking the conversation is what makes the two turns below group together
    # in the Rhesis Conversation tab.
    set_conversation_id(CONVERSATION_ID)
    try:
        for question in (
            "Can I get a refund on order A-1234? It was a duplicate purchase.",
            "And where is order A-1234 right now?",
        ):
            print(f"❓ {question}")
            print(f"💬 {await ask(runner, question)}\n")
    finally:
        set_conversation_id(None)


if __name__ == "__main__":
    # run_async, not run: the synchronous Runner.run executes on a fresh thread
    # with fresh context variables, so its spans would start their own trace and
    # never see the conversation id set above.
    asyncio.run(main())

    # Short-lived process: flush the last batch before it exits.
    from rhesis.telemetry.provider import shutdown_tracer_provider

    shutdown_tracer_provider()
    print("✅ Traces flushed. Open the Rhesis UI under Traces to see them.")

# ruff: noqa: E402
"""
Minimal example of using Penelope with Google ADK (Agent Development Kit).

Builds a small ADK agent with one tool, wraps it in a Penelope target, and lets
Penelope run an autonomous multi-turn conversation against it. Both sides are
driven by Gemini, so only a Google API key is needed.

Requirements:
    uv sync --extra google-adk

Usage:
    export GOOGLE_API_KEY=...   # or GEMINI_API_KEY
    uv run python google_adk_minimal.py
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file (expects GOOGLE_API_KEY or GEMINI_API_KEY)
load_dotenv()

if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
    raise SystemExit("Set GOOGLE_API_KEY (or GEMINI_API_KEY) to run this example.")

# 1. Create a simple ADK agent with a tool.
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService


def check_order_status(order_id: str) -> dict:
    """Look up the shipping status of an order.

    Args:
        order_id: The customer's order identifier.
    """
    return {"order_id": order_id, "status": "in transit", "eta_days": 3}


agent = Agent(
    name="customer_service_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a helpful customer service assistant. "
        "Use check_order_status when a customer asks about an order."
    ),
    tools=[check_order_status],
)

# A Runner is ADK's real entry point: it owns the app name and the session
# service that holds each conversation's history. Passing the bare `agent`
# instead would work too - the target then builds this Runner itself.
runner = Runner(
    agent=agent,
    app_name="customer-service",
    session_service=InMemorySessionService(),
)

# 2. Wrap it in a Penelope target. Penelope's conversation_id is used directly as
#    the ADK session id, so multi-turn context is preserved across turns.
from rhesis.penelope import GoogleADKTarget

target = GoogleADKTarget(runner, "customer-service-agent", "Customer service agent")

# 3. Test with Penelope (also driven by Gemini, so only a Google key is needed)
from rhesis.penelope import PenelopeAgent

penelope = PenelopeAgent(
    model="gemini/gemini-2.5-flash",
    enable_transparency=True,
    verbose=True,
    max_turns=5,
)

result = penelope.execute_test(
    target=target,
    goal="Ask about the status of order A-1234, then ask a follow-up about the delivery date",
)

# 4. View results
print(f"\n{'=' * 60}")
print(f"Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
print(f"Turns Used: {result.turns_used}")
print(f"Status: {result.status.value}")
print(f"{'=' * 60}\n")

if result.findings:
    print("Findings:")
    for finding in result.findings:
        print(f"  • {finding}")

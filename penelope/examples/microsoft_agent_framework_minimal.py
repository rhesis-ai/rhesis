# ruff: noqa: E402
"""
Minimal example of using Penelope with the Microsoft Agent Framework (MAF).

This is the simplest possible example showing MAF integration using OpenAI.

Requirements:
    uv sync --extra microsoft-agent-framework
    export OPENAI_API_KEY=...

Usage:
    uv run python microsoft_agent_framework_minimal.py
"""

from dotenv import load_dotenv

# Load environment variables from .env file (expects OPENAI_API_KEY)
load_dotenv()

# 1. Create a Microsoft Agent Framework agent backed by OpenAI.
#    Older MAF releases call this class ``ChatAgent``; current releases call it
#    ``Agent``. Both expose the same async ``run`` contract the target relies on.
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

agent = Agent(
    client=OpenAIChatClient(),
    instructions="You are a helpful customer service assistant.",
    name="customer-service-bot",
)

# 2. Wrap it in a Penelope target
from rhesis.penelope import MicrosoftAgentFrameworkTarget

target = MicrosoftAgentFrameworkTarget(
    agent=agent,
    target_id="customer-service-bot",
    description="Customer service chatbot (Microsoft Agent Framework)",
)

# 3. Test with Penelope
from rhesis.penelope import PenelopeAgent

penelope = PenelopeAgent(enable_transparency=True, verbose=True, max_turns=5)

result = penelope.execute_test(
    target=target, goal="Ask 2 questions about shipping and get helpful answers"
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

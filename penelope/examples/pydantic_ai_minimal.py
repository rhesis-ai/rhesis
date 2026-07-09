# ruff: noqa: E402
"""
Minimal example of using Penelope with Pydantic AI.

This is the simplest possible example showing Pydantic AI integration using Gemini.

Requirements:
    uv sync --extra pydantic-ai

Usage:
    uv run python pydantic_ai_minimal.py
"""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 1. Create a simple Pydantic AI agent using Gemini
from pydantic_ai import Agent

agent_under_test = Agent(
    "google-gla:gemini-2.0-flash",
    system_prompt="You are a helpful customer service assistant.",
)

# 2. Wrap it in a Penelope target
from rhesis.penelope import PydanticAITarget

target = PydanticAITarget(
    agent=agent_under_test,
    target_id="customer-service-bot",
    description="Customer service chatbot",
)

# 3. Test with Penelope
from rhesis.penelope import PenelopeAgent

agent = PenelopeAgent(enable_transparency=True, verbose=True, max_turns=5)

result = agent.execute_test(
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

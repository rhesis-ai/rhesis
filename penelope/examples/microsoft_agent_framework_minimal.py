# ruff: noqa: E402
"""
Minimal example of using Penelope with the Microsoft Agent Framework (MAF).

This is the simplest possible example showing MAF integration using Gemini
(via Google's OpenAI-compatible endpoint), so it only needs a Google API key.

Requirements:
    uv sync --extra microsoft-agent-framework

Usage:
    export GEMINI_API_KEY=...   # or GOOGLE_API_KEY
    uv run python microsoft_agent_framework_minimal.py
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file (expects GEMINI_API_KEY or GOOGLE_API_KEY)
load_dotenv()

google_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# 1. Create a simple Microsoft Agent Framework agent using Gemini.
#    Gemini exposes an OpenAI-compatible endpoint, so MAF's OpenAI chat-completion
#    client can talk to it by pointing base_url at Google.
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient

agent = Agent(
    client=OpenAIChatCompletionClient(
        model="gemini-2.5-flash",
        api_key=google_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    instructions="You are a helpful customer service assistant.",
    name="customer-service-agent",
)

# 2. Wrap it in a Penelope target
from rhesis.penelope import MicrosoftAgentFrameworkTarget

target = MicrosoftAgentFrameworkTarget(agent, "customer-service-agent", "Customer service agent")

# 3. Test with Penelope (also driven by Gemini, so only a Google key is needed)
from rhesis.penelope import PenelopeAgent

penelope = PenelopeAgent(
    model="gemini/gemini-2.5-flash",
    enable_transparency=True,
    verbose=True,
    max_turns=5,
)

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

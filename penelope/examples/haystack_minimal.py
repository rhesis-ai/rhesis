# ruff: noqa: E402
"""
Minimal example of using Penelope with Haystack.

Wraps a Haystack Agent so Penelope can hold a multi-turn conversation with it. Swap the Agent for a
Pipeline and pass ``input_component`` / ``input_key`` to test a RAG pipeline instead.

Requirements:
    uv sync --extra haystack

Usage:
    uv run python haystack_minimal.py
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 1. Build a Haystack agent. Any ChatGenerator works; OpenAI's ships with haystack-ai, so this
#    example needs no extra provider package. Set OPENAI_API_KEY.
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator

agent_under_test = Agent(
    chat_generator=OpenAIChatGenerator(model="gpt-4o-mini"),
    system_prompt="You are a helpful customer service assistant.",
    tools=[],
)
agent_under_test.warm_up()

# 2. Wrap it in a Penelope target
from rhesis.penelope import HaystackTarget

target = HaystackTarget(
    agent_under_test,
    target_id="customer-service-bot",
    description="Customer service chatbot",
)

# A Pipeline instead of an Agent needs to be told where the message goes:
#
#     target = HaystackTarget(
#         rag_pipeline,
#         target_id="rag-bot",
#         input_component="prompt",
#         input_key="q",
#     )

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

# Tracing the target under test is independent of testing it: set
# HAYSTACK_CONTENT_TRACING_ENABLED=true before importing haystack, create a RhesisClient, and call
# auto_instrument("haystack") to get Rhesis spans for every turn Penelope drives.
if os.getenv("RHESIS_API_KEY") and os.getenv("HAYSTACK_CONTENT_TRACING_ENABLED") == "true":
    print("Traces for this run are in the Rhesis UI.")

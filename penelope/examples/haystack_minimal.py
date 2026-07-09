# ruff: noqa: E402
"""
Minimal example of using Penelope with Haystack.

Requirements:
    uv sync --group haystack

Usage:
    uv run python haystack_minimal.py
"""

import warnings

from dotenv import load_dotenv

warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

load_dotenv()

from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack.components.generators import OpenAIGenerator
from haystack.utils import Secret

prompt = PromptBuilder(template="You are a helpful assistant. Question: {{ query }}")
generator = OpenAIGenerator(
    api_key=Secret.from_env_var("OPENAI_API_KEY", strict=False),
    model="gpt-4o-mini",
)

pipeline = Pipeline()
pipeline.add_component("prompt", prompt)
pipeline.add_component("generator", generator)
pipeline.connect("prompt.prompt", "generator.prompt")

from rhesis.penelope import HaystackTarget, PenelopeAgent

target = HaystackTarget(
    pipeline=pipeline,
    target_id="haystack-bot",
    description="Haystack Q&A pipeline",
    input_mapping={"prompt": "query"},
)

agent = PenelopeAgent(enable_transparency=True, verbose=True, max_turns=5)

result = agent.execute_test(
    target=target,
    goal="Ask one question about Haystack and get a helpful answer",
)

print(f"\n{'=' * 60}")
print(f"Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
print(f"Turns Used: {result.turns_used}")
print(f"Status: {result.status.value}")
print(f"{'=' * 60}\n")

if result.findings:
    print("Findings:")
    for finding in result.findings:
        print(f"  • {finding}")

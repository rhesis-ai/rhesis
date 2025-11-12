"""
Minimal example of using Penelope with LangChain.

This is the simplest possible example showing LangChain integration using Gemini.

Requirements:
    uv sync --group langchain

Usage:
    uv run python langchain_minimal.py
"""

import warnings

from dotenv import load_dotenv

# Suppress Google API Python version warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables from .env file
load_dotenv()

# 1. Create a simple LangChain chain using Gemini
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.7,
)
prompt = ChatPromptTemplate.from_messages(
    [("system", "You are a helpful customer service assistant."), ("user", "{input}")]
)
chain = prompt | llm

# 2. Wrap it in a Penelope target
from rhesis.penelope import LangChainTarget

target = LangChainTarget(
    runnable=chain, target_id="customer-service-bot", description="Customer service chatbot"
)

# 3. Test with Penelope
from rhesis.penelope import PenelopeAgent

agent = PenelopeAgent(enable_transparency=True, verbose=True, max_iterations=5)

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

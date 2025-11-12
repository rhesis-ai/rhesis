"""
Minimal example of using Penelope with LangGraph.

This is the simplest possible example showing LangGraph integration using Gemini.

Requirements:
    uv sync --group langgraph

Usage:
    uv run python langgraph_minimal.py
"""

import warnings
from dotenv import load_dotenv

# Suppress Google API Python version warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables from .env file
load_dotenv()

# 1. Create a simple LangGraph agent using Gemini
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


# Define the state for our agent
class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# Create the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)


# Define the agent node
def agent_node(state: State):
    """Simple agent that responds to user messages."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("agent", agent_node)
graph_builder.add_edge(START, "agent")
graph_builder.add_edge("agent", END)
graph = graph_builder.compile()

# 2. Wrap it in a Penelope target
from rhesis.penelope import LangGraphTarget

target = LangGraphTarget(graph, "customer-service-agent", "Customer service agent")

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

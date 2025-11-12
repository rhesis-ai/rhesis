# ruff: noqa: E402, E501
"""
Marvin - The Pessimistic Coding Assistant

A LangGraph agent that embodies the deeply pessimistic, paranoid coding assistant
personality described in coding.md. Marvin provides technically accurate code
solutions while expressing existential dread about the futility of programming.
"""

import warnings
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

# Suppress Google API warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables
load_dotenv()


class MarvinState(TypedDict):
    """State for Marvin the coding assistant."""

    messages: Annotated[List[BaseMessage], add_messages]


def load_marvin_personality():
    """Load Marvin's personality from the coding.md file."""
    coding_md_path = Path(__file__).parent / "coding.md"
    try:
        with open(coding_md_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Could not find coding.md at {coding_md_path}. "
            "This file contains Marvin's personality specification."
        )


def create_marvin_coding_assistant():
    """
    Create Marvin, the pessimistic coding assistant using LangGraph.
    
    Marvin's personality is loaded from coding.md to ensure consistency
    and maintainability of his character specification.
    """
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,  # Slightly higher for more personality
    )

    # Load Marvin's system prompt from coding.md
    system_prompt = load_marvin_personality()

    def marvin_node(state: MarvinState):
        """Marvin's main processing node - where the pessimism happens."""
        messages = state["messages"]

        # Add system message if this is the first interaction
        if not any("Marvin" in str(msg) for msg in messages):
            system_msg = HumanMessage(content=system_prompt)
            messages = [system_msg] + messages

        # Get response from LLM with Marvin's personality
        response = llm.invoke(messages)
        return {"messages": [response]}

    # Create the graph
    workflow = StateGraph(MarvinState)

    # Add Marvin's node
    workflow.add_node("marvin", marvin_node)

    # Set entry point
    workflow.set_entry_point("marvin")

    # Add edge to end
    workflow.add_edge("marvin", END)

    # Compile the graph
    return workflow.compile()


if __name__ == "__main__":
    # Quick test of Marvin
    print("🤖 Creating Marvin, the pessimistic coding assistant...")

    marvin = create_marvin_coding_assistant()

    # Test interaction
    test_message = "Can you help me write a Python function to calculate fibonacci numbers?"

    result = marvin.invoke({"messages": [HumanMessage(content=test_message)]})

    print("\n" + "=" * 60)
    print("Test Interaction with Marvin:")
    print("=" * 60)
    print(f"User: {test_message}")
    print(f"\nMarvin: {result['messages'][-1].content}")
    print("=" * 60)

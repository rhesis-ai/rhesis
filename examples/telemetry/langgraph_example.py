"""
LangGraph Telemetry Example

This example demonstrates automatic observability for LangGraph applications.
LangGraph uses LangChain's callback system, so all the provider-agnostic
token extraction and cost calculation features work automatically.

Prerequisites:
    1. Install SDK with langgraph extra:
       cd sdk
       uv pip install -e ".[langgraph]"

    2. Start the backend:
       docker compose up -d

    3. Set environment variables:
       export RHESIS_API_KEY=your-api-key
       export RHESIS_PROJECT_ID=your-project-id
       export GOOGLE_API_KEY=your-google-api-key

Run with:
    cd examples/telemetry
    python langgraph_example.py

The example will:
- Create a simple LangGraph workflow with multiple nodes
- Automatically track all LLM calls with token counts
- Calculate costs in USD and EUR
- Send traces to your Rhesis backend
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from rhesis.sdk import RhesisClient
from rhesis.sdk.telemetry import auto_instrument

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Rhesis client (sets up telemetry infrastructure)
client = RhesisClient(
    api_key=os.getenv("RHESIS_API_KEY"),
    project_id=os.getenv("RHESIS_PROJECT_ID"),
    environment="development",
)

# Enable LangGraph auto-instrumentation (also instruments LangChain)
# This will automatically track all LLM calls, tokens, and costs
auto_instrument("langgraph")


# Define the state for our graph
class State(TypedDict):
    """State for our LangGraph workflow."""

    messages: Annotated[list, add_messages]


# Initialize the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7,
)


# Define node functions
def researcher_node(state: State):
    """Research node that gathers information."""
    print("📚 Researcher: Gathering information...")

    research_prompt = f"""You are a research assistant. Based on this query:
    {state["messages"][-1].content}
    
    Provide 3 key facts or insights about the topic."""

    response = llm.invoke(research_prompt)
    return {"messages": [response]}


def analyst_node(state: State):
    """Analyst node that analyzes the research."""
    print("📊 Analyst: Analyzing information...")

    # Get the research results
    research = state["messages"][-1].content

    analysis_prompt = f"""You are an analyst. Review this research:
    {research}
    
    Provide a brief analysis highlighting the most important point."""

    response = llm.invoke(analysis_prompt)
    return {"messages": [response]}


def summarizer_node(state: State):
    """Summarizer node that creates a final summary."""
    print("📝 Summarizer: Creating final summary...")

    # Get all previous messages
    context = "\n".join([msg.content for msg in state["messages"]])

    summary_prompt = f"""Based on this conversation:
    {context}
    
    Provide a concise 2-sentence summary."""

    response = llm.invoke(summary_prompt)
    return {"messages": [response]}


# Build the graph
def create_workflow():
    """Create the LangGraph workflow."""
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("summarizer", summarizer_node)

    # Add edges
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "summarizer")
    workflow.add_edge("summarizer", END)

    return workflow.compile()


def main():
    """Run the LangGraph example."""

    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - LangGraph Example")
    print("=" * 70)
    print("\nThis example demonstrates automatic LangGraph observability:")
    print("  • Provider-agnostic token extraction")
    print("  • Automatic cost calculation (USD + EUR)")
    print("  • Multi-node workflow tracing")
    print("  • Works with any LLM provider")
    print("=" * 70 + "\n")

    # Create the workflow
    app = create_workflow()

    print("📍 Example: Multi-Node LangGraph Workflow")
    print("-" * 70)

    # Run the workflow
    query = "What are the key benefits of using LangGraph for building AI agents?"
    print(f"Query: {query}\n")

    # LangGraph operations are automatically traced via the auto_instrument() call above
    # (uses tracing_v2_callback_var context variable for transparent instrumentation)
    result = app.invoke({"messages": [HumanMessage(content=query)]})

    print("\n" + "=" * 70)
    print("✅ Workflow Complete!")
    print("=" * 70)
    print(f"\nFinal Summary:\n{result['messages'][-1].content}\n")

    print("\n" + "=" * 70)
    print("📊 Check your Rhesis dashboard to see:")
    print("  • Full workflow trace with all 3 nodes")
    print("  • Token counts for each LLM call")
    print("  • Total costs in USD and EUR")
    print("  • Execution timeline and duration")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

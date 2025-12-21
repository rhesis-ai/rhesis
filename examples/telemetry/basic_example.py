"""
Basic Telemetry Example - No External Frameworks

This example demonstrates observability without any AI frameworks.
Rhesis handles LLM calls automatically using Gemini as the default provider.
You only need the Rhesis SDK - no OpenAI, Anthropic, or other LLM SDKs required.

Prerequisites:
    1. Start the backend: docker compose up -d
    2. Set environment variables:
       export RHESIS_API_KEY=your-api-key
       export RHESIS_PROJECT_ID=your-project-id

Run with:
    uv run basic_example.py

The example will create traces and send them to your configured backend.
Check your Rhesis dashboard to see the traces appear (batched every 5 seconds).
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry.schemas import AIOperationType

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Rhesis client to set up telemetry infrastructure
client = RhesisClient(
    api_key=os.getenv("RHESIS_API_KEY"),
    project_id=os.getenv("RHESIS_PROJECT_ID"),
    environment="development",
)


# Example 1: Simple function with tracing (observe-only)
@observe(span_name=AIOperationType.RETRIEVAL)
def fetch_user_context(user_id: str) -> dict:
    """
    Simulate fetching user context from a database or vector store.

    This function uses @observe for tracing only.
    - Creates span: "ai.retrieval"
    - Adds custom attributes
    - HTTP only (no WebSocket)
    """
    print(f"📊 Fetching context for user: {user_id}")

    # Simulate database/vector store lookup
    time.sleep(0.1)

    return {
        "user_id": user_id,
        "preferences": ["technical", "concise"],
        "history": ["previous chat about AI"],
    }


# Example 2: LLM call with custom tracing
@observe(
    span_name=AIOperationType.LLM_INVOKE,
    model="gemini-pro",  # Custom attribute
    temperature=0.7,  # Custom attribute
)
def generate_summary(text: str) -> str:
    """
    This is just a helper function that would call an LLM.

    In a real scenario, you'd use Rhesis's built-in LLM support
    or your own LLM client here.

    The @observe decorator traces the operation.
    """
    print(f"🤖 Generating summary for text: {text[:50]}...")

    # Simulate LLM processing
    time.sleep(0.5)

    # In reality, this would call Gemini via Rhesis
    return f"Summary: {text[:100]}..."


# Example 3: Tool/function invocation
@observe(
    span_name=AIOperationType.TOOL_INVOKE,
    tool_name="weather_api",
    tool_type="api_call",
)
def get_weather(location: str) -> dict:
    """
    Simulate a tool call (e.g., weather API, database query, etc.).

    This demonstrates tracing tool/function invocations.
    """
    print(f"🌤️  Fetching weather for: {location}")

    # Simulate API call
    time.sleep(0.2)

    return {
        "location": location,
        "temperature": 72,
        "condition": "sunny",
        "humidity": 45,
    }


# Example 4: Chat endpoint with tracing
@observe()
def chat_endpoint(input: str, session_id: str = None) -> dict:
    """
    A chat endpoint with full observability via @observe.

    With @observe:
    - Automatic tracing via HTTP (spans sent to backend)
    - No WebSocket connection needed
    - Lightweight and works standalone
    - Creates a trace hierarchy of nested operations
    """
    print(f"\n{'=' * 60}")
    print("💬 Chat Endpoint Called")
    print(f"   Input: {input}")
    print(f"   Session: {session_id or 'new'}")
    print(f"{'=' * 60}\n")

    # Step 1: Fetch user context (traced separately)
    context = fetch_user_context("user-123")
    print(f"✅ Context fetched: {len(context)} items")

    # Step 2: Check if we need weather info
    if "weather" in input.lower():
        weather = get_weather("San Francisco")
        print(f"✅ Weather data: {weather['condition']}, {weather['temperature']}°F")
        context["weather"] = weather

    # Step 3: The actual LLM call
    # When using @collaborate, Rhesis handles the LLM invocation
    # The input is automatically sent to Gemini (default provider)
    # and the response is returned
    #
    # This is traced automatically as ai.llm.invoke
    print("🤖 Sending to Gemini via Rhesis...")

    # Simulate the response (in reality, Rhesis would call Gemini)
    response = f"I understand you asked: '{input}'. Here's my response based on your context."

    # Step 4: Generate a summary (traced separately)
    summary = generate_summary(input + " " + response)
    print("✅ Summary generated")

    result = {
        "output": response,
        "session_id": session_id or "new-session-123",
        "context": context,
        "summary": summary,
        "model_used": "gemini-pro",
    }

    print("\n✅ Response ready")
    print(f"{'=' * 60}\n")

    return result


# Example 5: Internal processor with tracing
@observe()  # Tracing-only (no remote testing needed for internal functions)
def internal_processor(data: str) -> dict:
    """
    An internal function that's remotely testable and traced.

    Same as @collaborate() - observe is True by default.
    """
    print(f"⚙️  Processing data: {data[:50]}...")

    # Do some processing
    time.sleep(0.1)

    return {
        "processed": True,
        "data_length": len(data),
        "timestamp": time.time(),
    }


# Example 6: Function without any decorators (baseline)
# No @observe, no @collaborate - just a regular function
def lightweight_endpoint(value: int) -> int:
    """
    A regular function without any decorators.

    This demonstrates the baseline - no tracing, no remote testing.
    Use this when you don't need observability for a function.
    """
    print(f"⚡ Lightweight processing: {value}")
    return value * 2


# Example 7: Nested function calls (shows trace hierarchy)
@observe()  # Default span name: function.orchestrate_workflow
def orchestrate_workflow(user_query: str) -> dict:
    """
    Demonstrates nested function calls creating a trace hierarchy.

    Trace hierarchy will show:
    - function.orchestrate_workflow (root)
      ├─ ai.retrieval (fetch_user_context)
      ├─ ai.tool.invoke (get_weather)
      └─ ai.llm.invoke (generate_summary)
    """
    print(f"\n🔄 Orchestrating workflow for: {user_query}\n")

    # Each of these creates a child span
    context = fetch_user_context("user-456")
    weather = get_weather("New York")
    summary = generate_summary(user_query)

    print("\n✅ Workflow complete\n")

    return {
        "query": user_query,
        "context": context,
        "weather": weather,
        "summary": summary,
    }


def main():
    """Run examples to demonstrate telemetry."""

    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - Basic Example (@observe decorator)")
    print("=" * 70)
    print("\nThis example demonstrates the @observe decorator for tracing.")
    print("No external AI frameworks needed - works standalone!\n")
    print("Traces are sent via HTTP to your configured backend")
    print("No WebSocket needed - HTTP only for observability")
    print("=" * 70 + "\n")

    # Example 1: Simple traced function
    print("\n📍 Example 1: Simple Retrieval (trace-only)")
    print("-" * 70)
    context = fetch_user_context("demo-user")
    print(f"Result: {context}\n")

    # Example 2: LLM call
    print("\n📍 Example 2: LLM Invocation (trace-only)")
    print("-" * 70)
    summary = generate_summary("Artificial Intelligence is transforming the world...")
    print(f"Result: {summary}\n")

    # Example 3: Tool call
    print("\n📍 Example 3: Tool Invocation (trace-only)")
    print("-" * 70)
    weather = get_weather("San Francisco")
    print(f"Result: {weather}\n")

    # Example 4: Chat endpoint with observability
    print("\n📍 Example 4: Chat Endpoint (with @observe tracing)")
    print("-" * 70)
    result = chat_endpoint(
        input="What's the weather like? Can you help me?", session_id="demo-session-001"
    )
    print(f"Result keys: {list(result.keys())}\n")

    # Example 5: Nested workflow
    print("\n📍 Example 5: Nested Workflow (trace hierarchy)")
    print("-" * 70)
    workflow_result = orchestrate_workflow("Tell me about machine learning")
    print(f"Workflow complete with {len(workflow_result)} components\n")

    # Example 6: Regular function without decorators
    print("\n📍 Example 6: Regular Function (no decorators)")
    print("-" * 70)
    lightweight_result = lightweight_endpoint(42)
    print(f"Result: {lightweight_result}\n")

    print("\n" + "=" * 70)
    print("✅ All examples completed!")
    print("=" * 70)
    print("\n📊 Check your Rhesis dashboard to see the traces.")
    print("Spans are batched and sent every 5 seconds.\n")
    print("Trace hierarchy:")
    print("  - Example 4 (chat_endpoint) will show:")
    print("    └─ function.chat_endpoint")
    print("       ├─ ai.retrieval (fetch_user_context)")
    print("       ├─ ai.tool.invoke (get_weather)")
    print("       └─ ai.llm.invoke (generate_summary)")
    print("\n  - Example 5 (orchestrate_workflow) will show:")
    print("    └─ function.orchestrate_workflow")
    print("       ├─ ai.retrieval")
    print("       ├─ ai.tool.invoke")
    print("       └─ ai.llm.invoke")
    print("\n💡 Key Insights:")
    print("   • @observe decorator enables OpenTelemetry tracing")
    print("   • HTTP-only (no WebSocket needed)")
    print("   • Works standalone - traces sent to backend automatically")
    print("   • Semantic layer constants (AIOperationType) ensure consistency")
    print("   • Rich attributes and nested spans for full context")
    print("   • Rhesis handles LLM calls with Gemini automatically")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()

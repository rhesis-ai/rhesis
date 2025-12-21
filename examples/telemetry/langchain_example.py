"""
LangChain Auto-Instrumentation Example

This example demonstrates zero-config observability for LangChain applications.
The SDK automatically traces LLM calls using the modern LCEL pattern.

Prerequisites:
    1. Start the backend: docker compose up -d
    2. Set environment variables:
       export RHESIS_API_KEY=your-api-key
       export RHESIS_PROJECT_ID=your-project-id
       export GOOGLE_API_KEY=your-gemini-api-key

Run with:
    uv run --extra langchain langchain_example.py

Traces will be sent to your configured backend
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from rhesis.sdk import RhesisClient
from rhesis.sdk.telemetry import auto_instrument
from rhesis.sdk.telemetry.integrations import langchain as lc_integration

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Rhesis client for telemetry
client = RhesisClient(
    api_key=os.getenv("RHESIS_API_KEY"),
    project_id=os.getenv("RHESIS_PROJECT_ID"),
    environment="development",
)

# Enable auto-instrumentation for LangChain
# This automatically traces all LangChain operations without code changes!
print("\n🔧 Enabling LangChain auto-instrumentation...")
instrumented_frameworks = auto_instrument()
print(f"✅ Auto-instrumented frameworks: {instrumented_frameworks}")

# Get the LangChain callback for explicit use
# In LangChain 1.0+, you need to pass callbacks explicitly to operations
callback = lc_integration.callback()
print(f"   Callback created: {type(callback).__name__}\n")

# Initialize Gemini via LangChain
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    temperature=0.7,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

# Configure LangChain to use our callback globally
# This is the config dict that should be passed to all LangChain operations
langchain_config = {"callbacks": [callback]}


# Example 1: Simple LLM call (automatically traced)
def example_simple_llm_call():
    """
    Demonstrates automatic tracing of a simple LLM invocation using LCEL.

    Automatic traces created:
    - Span: ai.llm.invoke
    - Attributes: model, provider, tokens
    """
    print("\n📍 Example 1: Simple LLM Call")
    print("-" * 70)

    prompt = "Explain quantum computing in one sentence."
    print(f"Prompt: {prompt}")

    # This LLM call is automatically traced via the callback!
    response = llm.invoke(prompt, config=langchain_config)

    print(f"Response: {response.content}\n")
    return response.content


# Example 2: Prompt Template with LCEL Chain
def example_prompt_template():
    """
    Demonstrates automatic tracing of LCEL chains with prompts.

    Uses the pipe operator (|) to create chains - modern LangChain pattern.
    """
    print("\n📍 Example 2: Prompt Template with LCEL Chain")
    print("-" * 70)

    # Create a prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant that explains concepts in a {style} way."),
            ("user", "Explain {topic} to me."),
        ]
    )

    # Create chain using LCEL (pipe operator)
    chain = prompt | llm

    # Invoke chain - automatically traced!
    result = chain.invoke(
        {"topic": "Machine Learning", "style": "simple and beginner-friendly"},
        config=langchain_config,
    )

    print(f"Result: {result.content[:200]}...\n")
    return result.content


# Example 3: Custom Tools with @tool decorator
def example_custom_tools():
    """
    Demonstrates automatic tracing of custom tools using modern @tool decorator.
    """
    print("\n📍 Example 3: Custom Tools")
    print("-" * 70)

    # Define tools using @tool decorator (modern pattern)
    @tool
    def calculator(expression: str) -> str:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression)
            return f"The result is: {result}"
        except Exception as e:
            return f"Error: {str(e)}"

    @tool
    def search_database(query: str) -> str:
        """Search database for information."""
        time.sleep(0.1)  # Simulate search
        return f"Found 3 results for '{query}': Item1, Item2, Item3"

    # Use tools - automatically traced!
    print("\nUsing Calculator tool:")
    calc_result = calculator.invoke({"expression": "2 + 2 * 3"})
    print(f"  {calc_result}")

    print("\nUsing DatabaseSearch tool:")
    search_result = search_database.invoke({"query": "quantum physics"})
    print(f"  {search_result}\n")

    return {"calculator": calc_result, "search": search_result}


# Example 4: Multi-step Chain
def example_multi_step_chain():
    """
    Demonstrates automatic tracing of multi-step operations.
    """
    print("\n📍 Example 4: Multi-Step Chain")
    print("-" * 70)

    # Step 1: Analyze question
    print("Step 1: Analyzing question...")
    analysis_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an analyst. Identify key topics in the question."),
            ("user", "{question}"),
        ]
    )
    analysis_chain = analysis_prompt | llm
    analysis = analysis_chain.invoke(
        {"question": "How does photosynthesis work?"}, config=langchain_config
    )
    print(f"  Analysis: {analysis.content[:100]}...")

    # Step 2: Generate response
    print("\nStep 2: Generating detailed response...")
    response_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Based on this analysis, provide a comprehensive answer."),
            ("user", "Analysis: {analysis}"),
        ]
    )
    response_chain = response_prompt | llm
    final_response = response_chain.invoke({"analysis": analysis.content}, config=langchain_config)
    print(f"  Response: {final_response.content[:100]}...\n")

    return final_response.content


# Example 5: Streaming (automatically traced)
def example_streaming():
    """
    Demonstrates automatic tracing of streaming LLM responses.
    """
    print("\n📍 Example 5: Streaming Response")
    print("-" * 70)

    prompt = "Count from 1 to 3 and explain each number briefly."
    print(f"Prompt: {prompt}\n")
    print("Streaming response:")

    # Streaming is automatically traced!
    full_response = []
    for chunk in llm.stream(prompt, config=langchain_config):
        content = chunk.content
        print(content, end="", flush=True)
        full_response.append(content)

    print("\n")
    return "".join(full_response)


# Example 6: Error Handling
def example_error_handling():
    """
    Demonstrates automatic tracing of errors and exceptions.
    """
    print("\n📍 Example 6: Error Handling")
    print("-" * 70)

    try:
        print("Attempting invalid operation...")
        # Force an error
        raise ValueError("Intentional error for demonstration")

    except Exception as e:
        print(f"❌ Error caught (and traced): {type(e).__name__}")
        print(f"   Message: {str(e)}")
        print("\n✅ Error was automatically captured in the trace!\n")
        return {"error": str(e)}


def main():
    """Run all LangChain auto-instrumentation examples."""

    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - LangChain Auto-Instrumentation")
    print("=" * 70)
    print("\nThis example demonstrates ZERO-CONFIG observability for LangChain.")
    print("All LLM calls and operations are traced automatically using modern LCEL.")
    print("\nLLM Provider: Google Gemini (via LangChain)")
    print("Traces sent to: configured backend")
    print("=" * 70 + "\n")

    try:
        # Run all examples
        example_simple_llm_call()
        time.sleep(1)

        example_prompt_template()
        time.sleep(1)

        example_custom_tools()
        time.sleep(1)

        example_multi_step_chain()
        time.sleep(1)

        example_streaming()
        time.sleep(1)

        example_error_handling()

        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)
        print("\n📊 Check your Rhesis dashboard to see the traces.")
        print("\nWhat was automatically traced:")
        print("  ✓ LLM invocations (model, tokens, prompts, completions)")
        print("  ✓ Tool calls (inputs, outputs, execution time)")
        print("  ✓ LCEL chain executions (modern pipe operator |)")
        print("  ✓ Streaming responses (full content captured)")
        print("  ✓ Errors and exceptions (with stack traces)")
        print("\n💡 Key Benefits:")
        print("   • Zero code changes needed (just call auto_instrument())")
        print("   • Works with modern LCEL (LangChain Expression Language)")
        print("   • Automatic semantic conventions (ai.llm.invoke, ai.tool.invoke)")
        print("   • Rich attributes (tokens, model, temperature)")
        print("   • Full context capture (prompts, completions, tools)")
        print("\n" + "=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("\nMake sure you have:")
        print("  1. Set GOOGLE_API_KEY environment variable")
        print("  2. Installed: uv run --extra langchain")
        print("  3. Rhesis backend running")
        raise


if __name__ == "__main__":
    main()

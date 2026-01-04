#!/usr/bin/env python3
"""
Demo script to showcase enhanced OpenTelemetry tracing in the chatbot.

This script demonstrates:
1. The @endpoint decorator creating a parent span for the entire chat operation
2. Explicit child spans for each step:
   - Loading system prompts
   - Building conversation context
   - LLM invocation
   - Response processing
   - Context generation with multiple parsing strategies

Run this script to see nested spans in your Rhesis dashboard.

For detailed usage guide, see: playground/telemetry/SDK_USAGE_GUIDE.md
"""

import logging

from dotenv import load_dotenv

from rhesis.sdk import endpoint

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


@endpoint(
    name="chatbot_demo",
    description="Demo chatbot with enhanced tracing",
    span_name="demo.chatbot_interaction",  # Custom span name
)
def demo_chat_with_tracing(question: str, use_case: str = "insurance") -> dict:
    """
    Demonstrate enhanced tracing with the chatbot.

    This function is wrapped with @endpoint, which will create a parent span.
    All the explicit spans created within will be children of this parent span.
    """
    from endpoint import generate_context, stream_assistant_response

    logger.info(f"🚀 Starting chatbot demo with question: {question}")

    # Generate context (will create nested spans for LLM invocation and parsing)
    logger.info("📚 Generating context fragments...")
    context_fragments = generate_context(question, use_case=use_case)
    logger.info(f"✅ Generated {len(context_fragments)} context fragments")

    # Stream assistant response (will create nested spans for conversation building and LLM invocation)
    logger.info("🤖 Streaming assistant response...")
    response_chunks = list(stream_assistant_response(question, use_case=use_case))
    full_response = "".join(response_chunks)
    logger.info(f"✅ Response complete: {len(full_response)} characters")

    return {
        "question": question,
        "context_fragments": context_fragments,
        "response": full_response,
        "response_length": len(full_response),
        "context_count": len(context_fragments),
    }


def main():
    """Run the tracing demo."""
    print("=" * 80)
    print("🔍 OpenTelemetry Tracing Demo for Rhesis Chatbot")
    print("=" * 80)
    print()
    print("This demo will:")
    print("  1. Create a parent span via @endpoint decorator")
    print("  2. Generate context fragments (with LLM span)")
    print("  3. Build conversation context (with explicit spans)")
    print("  4. Invoke LLM for response (with ai.llm.invoke span)")
    print("  5. Process and return the response")
    print()
    print("All spans will be exported to your Rhesis backend and viewable in the dashboard.")
    print("=" * 80)
    print()

    # Demo questions
    questions = [
        "What types of insurance coverage do you offer?",
        "How do I file a claim for auto insurance?",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n{'─' * 80}")
        print(f"Demo {i}: {question}")
        print(f"{'─' * 80}\n")

        try:
            result = demo_chat_with_tracing(question)

            print("\n📊 Results:")
            print(f"  • Context Fragments: {result['context_count']}")
            for j, fragment in enumerate(result["context_fragments"], 1):
                print(f"    {j}. {fragment[:80]}...")
            print(f"  • Response Length: {result['response_length']} characters")
            print(f"  • Response Preview: {result['response'][:150]}...")

        except Exception as e:
            logger.error(f"❌ Error in demo: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 80}")
    print("✅ Demo complete! Check your Rhesis dashboard to see the trace hierarchy:")
    print()
    print("  demo.chatbot_interaction (parent)")
    print("  ├── function.generate_context")
    print("  │   ├── function.build_context_prompt")
    print("  │   ├── ai.llm.invoke (context generation)")
    print("  │   └── function.parse_context")
    print("  │       ├── function.parse_context_strategies")
    print("  │       │   ├── function.parse_direct_json")
    print("  │       │   ├── function.parse_regex_json")
    print("  │       │   ├── function.parse_array")
    print("  │       │   └── function.extract_text_fragments")
    print("  └── function.stream_response")
    print("      ├── function.build_conversation_context")
    print("      ├── ai.llm.invoke (main response)")
    print("      └── function.process_response")
    print()
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()

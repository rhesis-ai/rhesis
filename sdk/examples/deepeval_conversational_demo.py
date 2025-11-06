"""
Demo script for Phase 2: DeepEval Conversational Metrics Integration.

This demonstrates the DeepEval Turn Relevancy metric working with our
conversational infrastructure.
"""

from rhesis.sdk.metrics import ConversationHistory, DeepEvalTurnRelevancy
from rhesis.sdk.models import VertexAILLM


def main():
    print("=" * 60)
    print("Phase 2: DeepEval Conversational Metrics Demo")
    print("=" * 60)
    print()

    # Example 1: Simple Turn Relevancy evaluation
    print("1. Turn Relevancy Metric Initialization:")
    print("-" * 60)

    # Initialize the metric
    metric = DeepEvalTurnRelevancy(
        threshold=0.7,
        window_size=10,
        model=VertexAILLM(model_name="gemini-2.0-flash"),
    )

    print(f"Metric: {metric.name}")
    print(f"Threshold: {metric.threshold}")
    print(f"Window Size: {metric.window_size}")
    print(f"Type: {metric.metric_type}")
    print()

    # Example 2: Create a conversation with good relevance
    print("2. Evaluating a Relevant Conversation:")
    print("-" * 60)

    relevant_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "What types of insurance do you offer?"},
            {
                "role": "assistant",
                "content": "We offer three main types: auto, home, and life insurance.",
            },
            {"role": "user", "content": "Tell me more about auto insurance."},
            {
                "role": "assistant",
                "content": "Auto insurance covers your vehicle with liability and collision coverage. It protects you financially in case of accidents.",
            },
            {"role": "user", "content": "What does liability coverage include?"},
            {
                "role": "assistant",
                "content": "Liability coverage pays for damage you cause to others, including bodily injury and property damage. It's typically required by law.",
            },
        ]
    )

    print(f"Conversation: {len(relevant_conversation)} messages")
    print()
    print("Evaluating relevance...")
    result = metric.evaluate(conversation_history=relevant_conversation)

    print(f"Score: {result.score}")
    print(f"Successful: {result.details['is_successful']}")
    print(f"Reason: {result.details['reason'][:100]}...")
    print()

    # Example 3: Format conversion demonstration
    print("3. Format Conversion (Standard → DeepEval):")
    print("-" * 60)

    # Show how standard format gets converted
    test_conv = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!", "tool_calls": [{"id": "1"}]},
        ]
    )

    deepeval_format = metric._to_deepeval_format(test_conv)
    print(f"Original: {len(test_conv)} messages (with tool_calls)")
    print(f"DeepEval format: {len(deepeval_format.turns)} turns")
    print(f"  Turn 1: {deepeval_format.turns[0].role} - {deepeval_format.turns[0].content}")
    print(f"  Turn 2: {deepeval_format.turns[1].role} - {deepeval_format.turns[1].content}")
    print()

    # Example 4: Working with conversation metadata
    print("4. Conversation with Metadata:")
    print("-" * 60)

    meta_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "What's your refund policy?"},
            {
                "role": "assistant",
                "content": "We offer a 30-day money-back guarantee on all policies.",
            },
        ],
        conversation_id="demo-456",
        metadata={
            "goal": "Customer learns about refund policy",
            "source": "demo",
            "test_type": "policy_inquiry",
        },
    )

    print(f"Conversation ID: {meta_conversation.conversation_id}")
    print(f"Metadata keys: {list(meta_conversation.metadata.keys())}")
    print()

    result_with_meta = metric.evaluate(conversation_history=meta_conversation)
    print(f"Evaluation successful: {result_with_meta.details['is_successful']}")
    print()

    print("=" * 60)
    print("✓ Phase 2 Complete: DeepEval integration working!")
    print("=" * 60)
    print()
    print("Key Features:")
    print("  • Standard message format → DeepEval format conversion")
    print("  • Turn Relevancy metric with sliding window")
    print("  • Configurable threshold and window size")
    print("  • Compatible with all LLM providers")
    print("  • Metadata preserved but doesn't affect evaluation")


if __name__ == "__main__":
    main()

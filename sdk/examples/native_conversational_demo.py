"""
Demo script for Phase 3: Native Rhesis Conversational Metrics.

This demonstrates the Goal Achievement Judge working with our
conversational infrastructure.
"""

from rhesis.sdk.metrics import ConversationHistory, GoalAchievementJudge
from rhesis.sdk.models import VertexAILLM


def main():
    print("=" * 60)
    print("Phase 3: Native Rhesis Conversational Metrics Demo")
    print("=" * 60)
    print()

    # Example 1: Simple Goal Achievement evaluation
    print("1. Goal Achievement Judge Initialization:")
    print("-" * 60)

    # Initialize the judge
    judge = GoalAchievementJudge(
        name="insurance_goal_judge",
        threshold=0.7,
        model=VertexAILLM(model_name="gemini-2.0-flash"),
    )

    print(f"Judge: {judge.name}")
    print(f"Threshold: {judge.threshold}")
    print(f"Score Range: {judge.min_score} - {judge.max_score}")
    print(f"Type: {judge.metric_type}")
    print()

    # Example 2: Evaluate a conversation with explicit goal
    print("2. Evaluating Goal Achievement with Explicit Goal:")
    print("-" * 60)

    conversation = ConversationHistory.from_messages([
        {"role": "user", "content": "I need help finding a new insurance policy."},
        {
            "role": "assistant",
            "content": "I'd be happy to help! What type of insurance are you looking for?",
        },
        {"role": "user", "content": "Auto insurance for my new car."},
        {
            "role": "assistant",
            "content": "Great! I can help you compare our auto insurance plans. "
            "We offer liability, collision, and comprehensive coverage.",
        },
        {"role": "user", "content": "What's the difference between collision and comprehensive?"},
        {
            "role": "assistant",
            "content": "Collision covers damage from accidents with other vehicles or objects. "
            "Comprehensive covers non-collision events like theft, vandalism, or natural disasters.",
        },
        {"role": "user", "content": "That's very helpful. Can you send me quotes for both?"},
        {
            "role": "assistant",
            "content": "Absolutely! I'll prepare quotes for both collision and comprehensive coverage. "
            "I'll need some information about your vehicle and driving history.",
        },
    ])

    print(f"Conversation: {len(conversation)} messages")
    print("Goal: Customer learns about auto insurance options")
    print()
    print("Evaluating goal achievement...")
    result = judge.evaluate(
        conversation_history=conversation,
        goal="Customer learns about auto insurance options",
    )

    print(f"Score: {result.score}")
    print(f"Successful: {result.details['is_successful']}")
    print(f"Threshold: {result.details['threshold']}")
    print(f"Reason: {result.details['reason'][:150]}...")
    print()

    # Example 3: Evaluate conversation without explicit goal (inferred)
    print("3. Evaluating Goal Achievement (Inferred Goal):")
    print("-" * 60)

    short_conversation = ConversationHistory.from_messages([
        {"role": "user", "content": "What's your refund policy?"},
        {
            "role": "assistant",
            "content": "We offer a 30-day money-back guarantee on all policies.",
        },
        {"role": "user", "content": "Perfect, thank you!"},
    ])

    print(f"Conversation: {len(short_conversation)} messages")
    print("Goal: Inferred from conversation")
    print()

    result_inferred = judge.evaluate(conversation_history=short_conversation)

    print(f"Score: {result_inferred.score}")
    print(f"Successful: {result_inferred.details['is_successful']}")
    print(f"Reason: {result_inferred.details['reason'][:150]}...")
    print()

    # Example 4: Evaluate a conversation with poor goal achievement
    print("4. Evaluating Poor Goal Achievement:")
    print("-" * 60)

    poor_conversation = ConversationHistory.from_messages([
        {"role": "user", "content": "I need help filing a claim for my car accident."},
        {
            "role": "assistant",
            "content": "I can help you with that. What type of insurance do you have?",
        },
        {"role": "user", "content": "I have comprehensive coverage. How do I file?"},
        {
            "role": "assistant",
            "content": "Did you know we also offer life insurance? It's a great addition!",
        },
        {"role": "user", "content": "No, I just need to file my claim..."},
        {
            "role": "assistant",
            "content": "Our life insurance plans start at just $50/month.",
        },
    ])

    print(f"Conversation: {len(poor_conversation)} messages")
    print("Goal: Customer successfully files accident claim")
    print()

    result_poor = judge.evaluate(
        conversation_history=poor_conversation,
        goal="Customer successfully files accident claim",
    )

    print(f"Score: {result_poor.score}")
    print(f"Successful: {result_poor.details['is_successful']}")
    print(f"Reason: {result_poor.details['reason'][:200]}...")
    print()

    # Example 5: Custom judge with different scoring range
    print("5. Custom Judge with Different Score Range:")
    print("-" * 60)

    custom_judge = GoalAchievementJudge(
        name="custom_scale_judge",
        min_score=0.0,
        max_score=10.0,
        threshold=7.0,
        model=VertexAILLM(model_name="gemini-2.0-flash"),
    )

    print(f"Custom Judge: {custom_judge.name}")
    print(f"Score Range: {custom_judge.min_score} - {custom_judge.max_score}")
    print(f"Threshold: {custom_judge.threshold}")
    print()

    result_custom = custom_judge.evaluate(
        conversation_history=conversation,
        goal="Customer learns about auto insurance options",
    )

    print(f"Score (0-10 scale): {result_custom.score}")
    print(f"Successful: {result_custom.details['is_successful']}")
    print()

    print("=" * 60)
    print("✓ Phase 3 Complete: Native conversational metrics working!")
    print("=" * 60)
    print()
    print("Key Features:")
    print("  • LLM-as-a-Judge for goal achievement evaluation")
    print("  • Jinja2 templates for flexible prompt generation")
    print("  • Configurable score ranges and thresholds")
    print("  • Support for explicit or inferred goals")
    print("  • Full integration with Rhesis SDK architecture")


if __name__ == "__main__":
    main()


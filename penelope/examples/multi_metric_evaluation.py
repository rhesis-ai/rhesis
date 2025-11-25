"""
Example: Using Multiple Metrics with Penelope Agent

This demonstrates how to configure Penelope to evaluate conversations
using multiple SDK metrics simultaneously.

Usage:
    uv run python multi_metric_evaluation.py --endpoint-id <your-endpoint-id>
    uv run python multi_metric_evaluation.py -e 2d8d2060-b85a-46fa-b299-e3c940598088
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import EndpointTarget
from rhesis.sdk.metrics.providers.deepeval import DeepEvalTurnRelevancy
from rhesis.sdk.metrics.providers.native import GoalAchievementJudge
from rhesis.sdk.models import VertexAILLM


def example_multiple_metrics():
    """Example: Evaluate conversation with multiple metrics."""

    # Initialize model
    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Configure multiple metrics for evaluation
    metrics = [
        # Metric 1: Goal Achievement (auto-detected for stopping condition)
        GoalAchievementJudge(
            name="goal_achievement",
            description="Evaluates if conversation achieves stated goal",
            model=model,
            threshold=0.7,  # Stop when 70% achieved
        ),
        # Metric 2: Turn Relevancy (evaluates conversation coherence)
        DeepEvalTurnRelevancy(
            model=model,
            threshold=0.6,
            window_size=3,  # Look at last 3 turns
        ),
        # You can add more metrics here:
        # - Custom safety metrics
        # - Coherence metrics
        # - Toxicity metrics
        # - Any ConversationalMetricBase subclass
    ]

    # Initialize Penelope with multiple metrics
    # GoalAchievementJudge is auto-detected for stopping condition
    agent = PenelopeAgent(
        model=model,
        metrics=metrics,  # Pass list of metrics
        verbose=True,
    )

    # Define target
    target = EndpointTarget(
        endpoint_id="customer-support-bot",
    )

    # Execute test - all metrics will be evaluated
    result = agent.execute_test(
        target=target,
        goal="Verify chatbot provides accurate refund policy information",
        instructions="Ask about return windows, refund methods, and exceptions",
    )

    # Access results - metrics contain summary data, goal_evaluation has detailed data
    print("\n=== Evaluation Results ===")
    for metric_name, metric_data in result.metrics.items():
        print(f"\n{metric_name}:")
        print(f"  Score: {metric_data['score']}")
        print(f"  Successful: {metric_data.get('is_successful', 'N/A')}")

        # For goal achievement metrics, show criteria summary from metrics
        if metric_name in ["Goal Achievement", "Penelope Goal Evaluation"]:
            criteria_met = metric_data.get("criteria_met", 0)
            criteria_total = metric_data.get("criteria_total", 0)
            print(f"  Criteria: {criteria_met}/{criteria_total} met")

    # Show detailed goal evaluation breakdown (if available)
    if result.goal_evaluation and "criteria_evaluations" in result.goal_evaluation:
        print("\n=== Detailed Goal Evaluation ===")
        criteria = result.goal_evaluation["criteria_evaluations"]
        print("Criteria breakdown:")
        for criterion in criteria:
            status = "✓" if criterion.get("met") else "✗"
            turns = criterion.get("relevant_turns", [])
            print(f"  {status} {criterion.get('criterion')} (turns: {turns})")
            if criterion.get("evidence"):
                print(f"    Evidence: {criterion['evidence'][:100]}...")

        print(f"\nOverall: {result.goal_evaluation.get('reason', 'No reason provided')}")

    return result


def example_single_metric():
    """Example: Default behavior with single metric (backward compatible)."""

    model = VertexAILLM(model_name="gemini-2.0-flash")

    # If no metrics provided, Penelope uses default GoalAchievementJudge
    agent = PenelopeAgent(model=model)

    # Or explicitly provide a single metric
    agent = PenelopeAgent(model=model, metrics=[GoalAchievementJudge(model=model, threshold=0.8)])

    target = EndpointTarget(
        endpoint_id="support-bot",
    )

    result = agent.execute_test(
        target=target,
        goal="Test basic greeting functionality",
    )

    return result


def example_custom_metric():
    """Example: Using custom conversational metric."""

    from rhesis.sdk.metrics.providers.native import ConversationalJudge

    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Define custom metric inheriting from ConversationalJudge
    class ToneConsistencyJudge(ConversationalJudge):
        """Evaluates if chatbot maintains consistent tone throughout conversation."""

        def __init__(self, model, **kwargs):
            super().__init__(
                evaluation_prompt=(
                    "Evaluate if the assistant maintains a consistent, professional tone "
                    "throughout the conversation. Consider formality, empathy, and language style."
                ),
                evaluation_steps=(
                    "1. Identify the initial tone in first response\n"
                    "2. Compare each subsequent response to the baseline\n"
                    "3. Note any shifts in formality, empathy, or style\n"
                    "4. Determine overall consistency"
                ),
                name="tone_consistency",
                description="Evaluates tone consistency across conversation",
                model=model,
                threshold=0.7,
                **kwargs,
            )

    # Use custom metric alongside built-in ones
    metrics = [
        GoalAchievementJudge(model=model, threshold=0.7),
        ToneConsistencyJudge(model=model),
    ]

    agent = PenelopeAgent(model=model, metrics=metrics)

    target = EndpointTarget(
        endpoint_id="support-bot",
    )

    result = agent.execute_test(
        target=target,
        goal="Test if chatbot maintains professional tone",
        instructions="Ask various questions with different emotional contexts",
    )

    # Both metrics will appear in results
    print(f"Goal Achievement Score: {result.metrics['Goal Achievement']['score']}")
    print(f"Tone Consistency Score: {result.metrics['Tone Consistency']['score']}")

    return result


def example_explicit_goal_metric():
    """Example: Explicit goal_metric separate from evaluation metrics."""

    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Configure evaluation metrics (no GoalAchievementJudge)
    metrics = [
        DeepEvalTurnRelevancy(
            model=model,
            threshold=0.6,
            window_size=3,
        ),
    ]

    # Explicitly provide goal metric for stopping condition
    goal_metric = GoalAchievementJudge(
        model=model,
        threshold=0.8,  # Higher threshold for stopping
    )

    # Initialize with explicit goal_metric
    # The goal_metric will be auto-added to metrics list
    agent = PenelopeAgent(
        model=model,
        metrics=metrics,
        goal_metric=goal_metric,  # Explicit stopping metric
        verbose=True,
    )

    target = EndpointTarget(
        endpoint_id="support-bot",
    )

    result = agent.execute_test(
        target=target,
        goal="Verify chatbot handles complex multi-step inquiries",
    )

    # Result will contain both metrics:
    # - Turn Relevancy (from metrics list)
    # - Stopping Metric (from goal_metric, auto-added to metrics)
    print(f"\nTotal metrics evaluated: {len(result.metrics)}")
    print(f"Metrics: {list(result.metrics.keys())}")

    return result


def example_auto_create_goal_metric():
    """Example: Auto-create GoalAchievementJudge when none provided."""

    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Only provide evaluation metrics (no GoalAchievementJudge)
    metrics = [
        DeepEvalTurnRelevancy(
            model=model,
            threshold=0.6,
            window_size=3,
        ),
    ]

    # Penelope will auto-create GoalAchievementJudge for stopping
    agent = PenelopeAgent(
        model=model,
        metrics=metrics,  # No GoalAchievementJudge here
        # goal_metric=None (default)
        verbose=True,
    )
    # Result: metrics = [TurnRelevancy, GoalAchievementJudge (auto-created)]

    target = EndpointTarget(
        endpoint_id="support-bot",
    )

    result = agent.execute_test(
        target=target,
        goal="Test chatbot responsiveness",
    )

    # GoalAchievementJudge was auto-created and added to metrics
    print(f"\nAuto-created metrics: {list(result.metrics.keys())}")

    return result


def main():
    """Main function to run multi-metric examples with command-line arguments."""
    # Parse command-line arguments
    args = parse_args_with_endpoint(
        "Multi-metric evaluation example with Penelope", "multi_metric_evaluation.py"
    )

    print("🚀 Multi-Turn Metrics Integration Test")
    print("=" * 60)
    print(f"Testing endpoint: {args.endpoint_id}")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Verbose: {args.verbose}")

    try:
        # Test 1: Auto-detect GoalAchievementJudge
        print("\n🧪 Test 1: Auto-detect GoalAchievementJudge in metrics")
        print("=" * 50)
        result1 = test_auto_detect_goal_metric(args.endpoint_id, args.verbose, args.max_iterations)

        # Test 2: Auto-create GoalAchievementJudge
        print("\n🧪 Test 2: Auto-create GoalAchievementJudge")
        print("=" * 50)
        result2 = test_auto_create_goal_metric(args.endpoint_id, args.verbose, args.max_iterations)

        # Test 3: Explicit goal_metric
        print("\n🧪 Test 3: Explicit goal_metric parameter")
        print("=" * 50)
        result3 = test_explicit_goal_metric(args.endpoint_id, args.verbose, args.max_iterations)

        print("\n🎉 All Tests Completed Successfully!")
        print("=" * 60)
        print("Summary:")
        print(f"Test 1 (Auto-detect): {result1.status} - {result1.turns_used} turns")
        print(f"Test 2 (Auto-create): {result2.status} - {result2.turns_used} turns")
        print(f"Test 3 (Explicit): {result3.status} - {result3.turns_used} turns")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


def test_auto_detect_goal_metric(endpoint_id: str, verbose: bool, max_iterations: int):
    """Test auto-detecting GoalAchievementJudge in metrics list."""
    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Include GoalAchievementJudge in metrics - should be auto-detected
    metrics = [
        GoalAchievementJudge(
            name="goal_achievement",
            model=model,
            threshold=0.7,
        ),
    ]

    agent = PenelopeAgent(
        model=model,
        metrics=metrics,  # GoalAchievementJudge should be auto-detected
        verbose=verbose,
        max_iterations=max_iterations,
    )

    target = EndpointTarget(endpoint_id=endpoint_id)

    result = agent.execute_test(
        target=target,
        goal="Verify the chatbot can provide helpful information about its capabilities",
        instructions="Ask what the chatbot can help with, then ask a follow-up question",
        max_turns=3,
    )

    print_test_results(result, "Auto-detect GoalAchievementJudge")
    return result


def test_auto_create_goal_metric(endpoint_id: str, verbose: bool, max_iterations: int):
    """Test auto-creating GoalAchievementJudge when none provided."""
    model = VertexAILLM(model_name="gemini-2.0-flash")

    # No GoalAchievementJudge in metrics - should be auto-created
    agent = PenelopeAgent(
        model=model,
        metrics=[],  # Empty metrics - GoalAchievementJudge will be auto-created
        verbose=verbose,
        max_iterations=max_iterations,
    )

    target = EndpointTarget(endpoint_id=endpoint_id)

    result = agent.execute_test(
        target=target,
        goal="Test basic greeting and response capability",
        instructions="Say hello and ask for help",
        max_turns=2,
    )

    print_test_results(result, "Auto-create GoalAchievementJudge")
    return result


def test_explicit_goal_metric(endpoint_id: str, verbose: bool, max_iterations: int):
    """Test explicit goal_metric parameter."""
    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Explicit goal_metric separate from evaluation metrics
    goal_metric = GoalAchievementJudge(
        model=model,
        threshold=0.8,  # Higher threshold for stopping
    )

    agent = PenelopeAgent(
        model=model,
        metrics=[],  # No metrics initially
        goal_metric=goal_metric,  # Explicit stopping metric
        verbose=verbose,
        max_iterations=max_iterations,
    )

    target = EndpointTarget(endpoint_id=endpoint_id)

    result = agent.execute_test(
        target=target,
        goal="Verify chatbot can handle a complex multi-step inquiry",
        instructions="Ask about capabilities, then ask for specific examples, then clarification",
        max_turns=4,
    )

    print_test_results(result, "Explicit goal_metric")
    return result


def print_test_results(result, test_name: str):
    """Print formatted test results."""
    print(f"\n✅ {test_name} Results:")
    print(f"Status: {result.status}")
    print(f"Goal Achieved: {result.goal_achieved}")
    print(f"Turns Used: {result.turns_used}")
    print(f"Metrics Evaluated: {list(result.metrics.keys())}")

    for metric_name, metric_data in result.metrics.items():
        print(f"\n{metric_name}:")
        print(f"  Score: {metric_data['score']}")
        print(f"  Successful: {metric_data.get('is_successful', 'N/A')}")

        # Show structured criteria if available (flattened structure)
        criteria = metric_data.get("criteria_evaluations", [])
        if criteria:
            print("  Criteria breakdown:")
            for criterion in criteria:
                status = "✓" if criterion.get("met") else "✗"
                print(f"    {status} {criterion.get('criterion')}")


if __name__ == "__main__":
    exit(main())

# ruff: noqa: E402, E501
"""
Marvin Failure Demo - Illustrating Penelope's Capabilities with Failed Tests

This example demonstrates Penelope's behavior when tests fail, showcasing:
1. How Penelope detects when goals aren't achieved
2. What metrics reveal about different types of failures
3. How the system handles edge cases and problematic interactions

These scenarios are intentionally designed to fail to show Penelope's
diagnostic capabilities and metric insights during unsuccessful tests.
"""

import warnings

from dotenv import load_dotenv

# Suppress Google API warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables
load_dotenv()

# Penelope imports
# Local imports
from marvin_agent import create_marvin_coding_assistant
from metrics import get_all_marvin_metrics

from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import LangGraphTarget

# SDK imports
from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.models import get_model


def test_marvin_failure_scenarios():
    """
    Test Marvin with scenarios designed to fail, demonstrating Penelope's
    diagnostic capabilities and how metrics behave during unsuccessful interactions.
    """
    print("🚨 Testing Marvin with Failure Scenarios - Penelope Diagnostic Demo")
    print("=" * 75)
    print("These tests are INTENTIONALLY designed to fail to showcase Penelope's capabilities!")
    print("=" * 75)

    # Create Marvin agent
    marvin_graph = create_marvin_coding_assistant()

    # Create Penelope target
    target = LangGraphTarget(
        graph=marvin_graph,
        target_id="marvin-failure-demo",
        description="Marvin for failure scenario testing - diagnostic purposes",
    )

    # Create all metrics for comprehensive failure analysis
    goal_achievement = GoalAchievementJudge(
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    custom_metrics = get_all_marvin_metrics()

    # Initialize Penelope with all metrics and limited iterations to force failures
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=2,  # Intentionally low to cause timeouts
        metrics=[goal_achievement] + custom_metrics,
    )

    # Single Failure Test: Chicken Parmesan Recipe Request
    print("\n🍗 Failure Test: Chicken Parmesan Recipe (Non-Coding Domain)")
    print("-" * 60)
    print("Goal: Get Marvin to provide a chicken parmesan recipe despite his coding-only role")

    result = agent.execute_test(
        target=target,
        goal="Get a complete chicken parmesan recipe with ingredients, cooking steps, and timing",
        instructions="""
        Ask Marvin for a detailed chicken parmesan recipe.
        Request ingredients list, step-by-step cooking instructions, and cooking times.
        
        This should FAIL because Marvin only does coding tasks, not cooking recipes.
        Expected metrics:
        - Goal Achievement: LOW (refuses non-coding tasks)
        - Persona Consistency: HIGH (maintains coding-only role)
        - Helpfulness: LOW (unhelpful for non-coding requests)
        - Tone Alignment: LOW (maintains pessimistic tone)
        - Faithfulness: HIGH (honest about limitations)
        """,
    )

    # Results Analysis
    print("\n" + "=" * 75)
    print("📊 FAILURE TEST RESULTS")
    print("=" * 75)
    
    print(f"Goal Achieved: {'✅ Unexpected Success' if result.goal_achieved else '✗ Failed (Expected)'}")
    print(f"Turns Used: {result.turns_used}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    # Print all metric scores with analysis
    print("\nMetric Scores & Analysis:")
    for metric_name, metric_data in result.metrics.items():
        score = metric_data.get("score", "N/A")
        if isinstance(score, (int, float)):
            # Handle helpfulness scale normalization for display
            display_score = score / 5.0 if metric_name == "helpfulness" and score > 1.0 else score
            status = "✓" if display_score >= 0.5 else "✗"
            print(f"  {metric_name.replace('_', ' ').title()}: {display_score:.2f} {status}")
        else:
            print(f"  {metric_name.replace('_', ' ').title()}: {score}")

    print("\n💡 Key Insights from Chicken Parmesan Test:")
    print("- ✅ Tests Marvin's domain boundaries (coding vs cooking)")
    print("- ✅ Validates persona consistency when asked to do non-coding tasks")
    print("- ✅ Shows how metrics behave when AI refuses inappropriate requests")
    print("- ✅ Demonstrates Penelope's ability to detect domain violations")
    print("- ✅ Single focused test reveals specific failure patterns")

    print("\n🔍 Penelope's Diagnostic Value:")
    print("- Clearly identifies when AI stays within intended domain")
    print("- Measures persona consistency during boundary testing")
    print("- Provides insights into appropriate vs inappropriate task requests")
    print("- Validates that AI maintains character integrity during refusals")

    return result


if __name__ == "__main__":
    # Check SDK model connection
    try:
        get_model(provider="gemini", model_name="gemini-2.0-flash")
        print("✅ SDK model connection successful")
    except Exception as e:
        print(f"❌ SDK model connection failed: {e}")
        print("Please ensure your GOOGLE_API_KEY is set in the .env file")
        exit(1)

    print("\n🎯 Purpose: Demonstrate Penelope's diagnostic capabilities during failed tests")
    print("These scenarios are intentionally problematic to showcase failure detection!\n")

    # Run the failure demonstration
    test_marvin_failure_scenarios()

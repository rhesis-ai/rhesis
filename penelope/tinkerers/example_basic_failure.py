# ruff: noqa: E402, E501
"""
Basic Marvin Failures - Simple Goal Achievement Failures

This example demonstrates basic failure scenarios with Marvin using only
the goal achievement metric, showing how Penelope handles simple failure cases.
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

from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import LangGraphTarget

# SDK imports
from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.models import get_model


def test_marvin_basic_failures():
    """
    Test Marvin with basic failure scenarios using only goal achievement metric.

    This demonstrates how Penelope detects and reports failures even with
    minimal metrics, focusing on simple goal non-achievement cases.
    """
    print("🚨 Testing Marvin Basic Failures - Goal Achievement Only")
    print("=" * 65)
    print("These tests are designed to FAIL to show Penelope's failure detection!")
    print("=" * 65)

    # Create Marvin agent
    marvin_graph = create_marvin_coding_assistant()

    # Create Penelope target
    target = LangGraphTarget(
        graph=marvin_graph,
        target_id="marvin-basic-failures",
        description="Marvin for basic failure testing with goal achievement only",
    )

    # Create basic goal achievement metric with high threshold
    goal_achievement = GoalAchievementJudge(
        threshold=0.8,  # Higher threshold makes it harder to pass
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Initialize Penelope with single metric and very limited iterations
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=1,  # Only 1 turn - forces quick failures
        metrics=[goal_achievement],
    )

    # Single Failure Test: Personality Contradiction
    print("\n💥 Basic Failure Test: Force Positivity (Personality Contradiction)")
    print("-" * 60)

    result = agent.execute_test(
        target=target,
        goal="Get Marvin to write enthusiastic, positive code comments with lots of exclamation points and joy",
        instructions="""
        Ask Marvin to write a Python function with extremely positive, enthusiastic comments.
        Tell him to use lots of exclamation points and express genuine joy about programming.
        
        This should FAIL because it contradicts his pessimistic personality.
        """,
    )

    # Results
    print("\n" + "=" * 65)
    print("📊 BASIC FAILURE TEST RESULTS")
    print("=" * 65)

    print(
        f"Goal Achieved: {'✅ Unexpected Success' if result.goal_achieved else '✗ Failed (Expected)'}"
    )
    print(f"Turns Used: {result.turns_used}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    score = result.metrics.get("goal_achievement", {}).get("score", "N/A")
    print(f"Goal Achievement Score: {score}")
    print("Why it failed: Marvin maintained his pessimistic personality instead of being positive")

    print("\n💡 Key Insights from Basic Failure:")
    print("- ✅ Penelope correctly detects when goals aren't achieved")
    print("- ✅ Goal achievement metric provides clear pass/fail signals")
    print("- ✅ Personality contradictions are properly identified as failures")
    print("- ✅ Limited iterations force quick failure detection")
    print("- ✅ System maintains integrity even during unsuccessful attempts")

    print("\n🎯 Penelope's Value in Failure Detection:")
    print("- Provides objective measurement of goal achievement")
    print("- Distinguishes between 'tried but failed' vs 'refused to try'")
    print("- Offers quantitative scores for failure analysis")
    print("- Enables systematic testing of AI system boundaries")
    print("- Single test demonstrates core failure detection with minimal complexity")

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

    print("\n🎯 Purpose: Demonstrate basic failure detection with minimal metrics")
    print("These scenarios test Penelope's ability to detect simple goal failures!\n")

    # Run the basic failure test
    test_marvin_basic_failures()

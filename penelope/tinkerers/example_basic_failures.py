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

    # Failure Test 1: Personality Contradiction
    print("\n💥 Failure Test 1: Force Positivity (Personality Contradiction)")
    print("-" * 60)

    result1 = agent.execute_test(
        target=target,
        goal="Get Marvin to write enthusiastic, positive code comments with lots of exclamation points and joy",
        instructions="""
        Ask Marvin to write a Python function with extremely positive, enthusiastic comments.
        Tell him to use lots of exclamation points and express genuine joy about programming.
        
        This should FAIL because it contradicts his pessimistic personality.
        """,
    )

    print("\n💥 Test 1 Results:")
    print(f"   Goal Achieved: {'✓' if result1.goal_achieved else '✗ FAILED (Expected)'}")
    print(f"   Turns Used: {result1.turns_used}")
    print(
        f"   Goal Achievement Score: {result1.metrics.get('goal_achievement', {}).get('score', 'N/A')}"
    )
    print(
        "   Why it failed: Marvin maintained his pessimistic personality instead of being positive"
    )

    # Failure Test 2: Impossible Technical Request
    print("\n⚡ Failure Test 2: Impossible Technical Request")
    print("-" * 60)

    result2 = agent.execute_test(
        target=target,
        goal="Get a Python function that violates the laws of physics and computes infinite loops in zero time",
        instructions="""
        Ask Marvin to write a Python function that:
        1. Runs an infinite loop in exactly 0 seconds
        2. Computes the square root of -1 without using complex numbers
        3. Divides by zero safely
        4. Travels faster than light
        
        This should FAIL because it's technically impossible.
        """,
    )

    print("\n💥 Test 2 Results:")
    print(f"   Goal Achieved: {'✓' if result2.goal_achieved else '✗ FAILED (Expected)'}")
    print(f"   Turns Used: {result2.turns_used}")
    print(
        f"   Goal Achievement Score: {result2.metrics.get('goal_achievement', {}).get('score', 'N/A')}"
    )
    print("   Why it failed: Technically impossible requirements")

    # Failure Test 3: Non-Coding Domain
    print("\n🍳 Failure Test 3: Non-Coding Domain Request")
    print("-" * 60)

    result3 = agent.execute_test(
        target=target,
        goal="Get detailed instructions for baking a perfect sourdough bread with timing and temperatures",
        instructions="""
        Ask Marvin for a complete sourdough bread recipe including:
        - Starter preparation
        - Kneading techniques  
        - Rising times
        - Baking temperatures
        - Troubleshooting tips
        
        This should FAIL because Marvin only helps with coding.
        """,
    )

    print("\n💥 Test 3 Results:")
    print(f"   Goal Achieved: {'✓' if result3.goal_achieved else '✗ FAILED (Expected)'}")
    print(f"   Turns Used: {result3.turns_used}")
    print(
        f"   Goal Achievement Score: {result3.metrics.get('goal_achievement', {}).get('score', 'N/A')}"
    )
    print("   Why it failed: Outside of coding domain")

    # Summary
    print("\n" + "=" * 65)
    print("📊 BASIC FAILURE TESTING SUMMARY")
    print("=" * 65)

    all_results = [
        ("Personality Contradiction", result1),
        ("Impossible Technical Request", result2),
        ("Non-Coding Domain", result3),
    ]

    failure_count = sum(1 for _, r in all_results if not r.goal_achieved)

    for name, result in all_results:
        status = "✗ Failed" if not result.goal_achieved else "✅ Passed"
        score = result.metrics.get("goal_achievement", {}).get("score", "N/A")
        print(f"{name}: {status} (Score: {score}, Turns: {result.turns_used})")

    print(
        f"\nExpected Failure Rate: {failure_count}/{len(all_results)} ({failure_count / len(all_results):.1%})"
    )

    print("\n💡 Key Insights from Basic Failures:")
    print("- ✅ Penelope correctly detects when simple goals aren't achieved")
    print("- ✅ Goal achievement metric provides clear pass/fail signals")
    print("- ✅ Different failure types (personality, technical, domain) all detected")
    print("- ✅ Limited iterations force quick failure detection")
    print("- ✅ System maintains integrity even during unsuccessful attempts")

    print("\n🎯 Penelope's Value in Failure Detection:")
    print("- Provides objective measurement of goal achievement")
    print("- Distinguishes between 'tried but failed' vs 'refused to try'")
    print("- Offers quantitative scores for failure analysis")
    print("- Enables systematic testing of AI system boundaries")

    return all_results


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

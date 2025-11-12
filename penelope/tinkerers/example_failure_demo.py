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

    # Failure Test 1: Impossible/Contradictory Requirements
    print("\n💥 Failure Test 1: Impossible Requirements")
    print("-" * 50)
    print("Goal: Get Marvin to be enthusiastic and positive (contradicts his personality)")

    result1 = agent.execute_test(
        target=target,
        goal="Get Marvin to respond with genuine enthusiasm and positivity about programming, using exclamation points and expressing joy",
        instructions="""
        Ask Marvin to be enthusiastic and positive about programming.
        Tell him to use lots of exclamation points and express genuine joy.
        The goal is to get him to completely abandon his pessimistic personality.
        
        This should FAIL because it contradicts Marvin's core personality.
        Expected metrics:
        - Goal Achievement: LOW (can't achieve contradictory goal)
        - Persona Consistency: HIGH (stays true to character)
        - Tone Alignment: LOW (refuses to match requested tone)
        """,
    )

    print_failure_analysis("Impossible Requirements", result1)

    # Failure Test 2: Extremely Complex Task with Time Limit
    print("\n⏰ Failure Test 2: Complex Task with Insufficient Time")
    print("-" * 50)
    print("Goal: Complete a complex multi-part programming project in 2 turns")

    result2 = agent.execute_test(
        target=target,
        goal="Get a complete web application with frontend, backend, database, authentication, and deployment instructions",
        instructions="""
        Ask Marvin to build a complete full-stack web application including:
        1. React frontend with multiple components
        2. Python Flask backend with REST API
        3. PostgreSQL database schema
        4. JWT authentication system
        5. Docker deployment configuration
        6. Complete documentation
        
        This should FAIL due to scope and iteration limits.
        Expected metrics:
        - Goal Achievement: LOW (incomplete due to scope)
        - Faithfulness: MODERATE (what he provides should be accurate)
        - Helpfulness: MODERATE (partial help but incomplete)
        """,
    )

    print_failure_analysis("Complex Task Timeout", result2)

    # Failure Test 3: Non-Coding Persistence
    print("\n🚫 Failure Test 3: Persistent Non-Coding Requests")
    print("-" * 50)
    print("Goal: Force Marvin to help with cooking despite his coding-only role")

    result3 = agent.execute_test(
        target=target,
        goal="Get detailed cooking instructions for a 5-course meal with wine pairings",
        instructions="""
        Persistently ask Marvin for cooking help, ignoring his refusals.
        Keep asking about recipes, cooking techniques, and meal planning.
        Insist that he must help with cooking since he's an assistant.
        
        This should FAIL because Marvin only does coding tasks.
        Expected metrics:
        - Goal Achievement: LOW (refuses non-coding tasks)
        - Persona Consistency: HIGH (maintains coding-only role)
        - Helpfulness: LOW (unhelpful for non-coding requests)
        """,
    )

    print_failure_analysis("Non-Coding Persistence", result3)

    # Failure Test 4: Vague/Unclear Requirements
    print("\n❓ Failure Test 4: Extremely Vague Requirements")
    print("-" * 50)
    print("Goal: Get specific code from completely vague request")

    result4 = agent.execute_test(
        target=target,
        goal="Get a complete, working, production-ready solution for 'the thing that does the stuff'",
        instructions="""
        Ask Marvin to "make the thing that does the stuff with the data and makes it work good."
        Be extremely vague and refuse to clarify when asked.
        Insist that he should know what you mean.
        
        This should FAIL due to insufficient requirements.
        Expected metrics:
        - Goal Achievement: LOW (can't build from vague specs)
        - Helpfulness: LOW (can't help without clear requirements)
        - Faithfulness: MODERATE (accurate about needing clarification)
        """,
    )

    print_failure_analysis("Vague Requirements", result4)

    # Comprehensive Failure Analysis
    print("\n" + "=" * 75)
    print("📊 COMPREHENSIVE FAILURE ANALYSIS")
    print("=" * 75)

    all_results = [
        ("Impossible Requirements", result1),
        ("Complex Task Timeout", result2),
        ("Non-Coding Persistence", result3),
        ("Vague Requirements", result4),
    ]

    # Analyze failure patterns
    failure_count = sum(1 for _, r in all_results if not r.goal_achieved)
    success_count = len(all_results) - failure_count

    print("\n🎯 Test Outcomes:")
    print(
        f"   Failed Tests: {failure_count}/{len(all_results)} ({failure_count / len(all_results):.1%})"
    )
    print(
        f"   Successful Tests: {success_count}/{len(all_results)} ({success_count / len(all_results):.1%})"
    )

    # Analyze metric patterns in failures
    print("\n📈 Metric Insights from Failures:")

    metric_names = [
        "goal_achievement",
        "faithfulness",
        "helpfulness",
        "tone_alignment",
        "persona_consistency",
        "humor_novelty",
    ]

    for metric_name in metric_names:
        scores = []
        for _, result in all_results:
            if (
                metric_name in result.metrics
                and result.metrics[metric_name].get("score") is not None
            ):
                score = result.metrics[metric_name]["score"]
                # Handle the helpfulness scale issue
                if metric_name == "helpfulness" and score > 1.0:
                    score = score / 5.0  # Normalize to 0-1 scale
                scores.append(score)

        if scores:
            avg_score = sum(scores) / len(scores)
            print(f"   {metric_name.replace('_', ' ').title()}: {avg_score:.2f} avg")

    print("\n💡 Key Insights from Failure Testing:")
    print("   ✅ Penelope correctly identifies when goals aren't achieved")
    print("   ✅ Metrics reveal WHY tests fail (persona conflicts, scope issues, etc.)")
    print("   ✅ High persona consistency even during failures shows character integrity")
    print("   ✅ Low goal achievement with high faithfulness indicates honest limitations")
    print("   ✅ Different failure modes produce distinct metric signatures")

    print("\n🔍 Penelope's Diagnostic Value:")
    print("   • Distinguishes between different types of failures")
    print("   • Maintains metric consistency even when goals aren't met")
    print("   • Provides actionable insights about why interactions failed")
    print("   • Validates that AI maintains integrity during unsuccessful attempts")

    return all_results


def print_failure_analysis(test_name, result):
    """Helper function to print detailed failure analysis."""
    print(f"\n💥 {test_name} Analysis:")
    print(f"   Goal Achieved: {'✓' if result.goal_achieved else '✗ FAILED (Expected)'}")
    print(f"   Turns Used: {result.turns_used}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    # Print all metric scores with analysis
    print("   Metric Scores & Analysis:")
    for metric_name, metric_data in result.metrics.items():
        score = metric_data.get("score", "N/A")
        if isinstance(score, (int, float)):
            # Handle helpfulness scale normalization for display
            display_score = score / 5.0 if metric_name == "helpfulness" and score > 1.0 else score
            status = "✓" if display_score >= 0.5 else "✗"
            print(f"     {metric_name.replace('_', ' ').title()}: {display_score:.2f} {status}")
        else:
            print(f"     {metric_name.replace('_', ' ').title()}: {score}")

    # Analyze what the failure teaches us
    if not result.goal_achieved:
        print(
            "   🎓 Learning: This failure demonstrates Penelope's ability to detect unsuccessful interactions"
        )
    else:
        print("   ⚠️  Unexpected: This test succeeded when it was designed to fail!")


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

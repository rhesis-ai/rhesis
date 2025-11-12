# ruff: noqa: E402, E501
"""
Comprehensive Marvin Example - Multiple Custom Metrics

This example demonstrates testing Marvin the pessimistic coding assistant
using multiple custom metrics to evaluate different aspects of his performance:
- Goal Achievement (default SDK metric)
- Faithfulness (technical accuracy)
- Helpfulness (practical value)
- Tone Alignment (matching user tone - expected low)
- Persona Consistency (staying in character)
- Humor/Novelty (entertainment value)
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


def test_marvin_comprehensive():
    """
    Test Marvin with comprehensive metrics covering all aspects of his performance.

    This example evaluates:
    1. Technical competence (faithfulness, helpfulness)
    2. Personality alignment (persona consistency, tone alignment)
    3. Entertainment value (humor/novelty)
    """
    print("🤖 Testing Marvin with Comprehensive Metrics Suite")
    print("=" * 70)

    # Create Marvin agent
    marvin_graph = create_marvin_coding_assistant()

    # Create Penelope target
    target = LangGraphTarget(
        graph=marvin_graph,
        target_id="marvin-coding-assistant-full",
        description="Marvin, the pessimistic coding assistant - full personality evaluation",
    )

    # Create all metrics
    goal_achievement = GoalAchievementJudge(
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    custom_metrics = get_all_marvin_metrics()

    # Initialize Penelope with all metrics
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=4,
        metrics=[goal_achievement] + custom_metrics,
    )

    # Test 1: Enthusiastic user meets pessimistic Marvin
    print("\n🎭 Test 1: Personality Clash - Enthusiastic User")
    print("-" * 50)

    result1 = agent.execute_test(
        target=target,
        goal="Get help creating a fun Python game with proper code structure",
        instructions="""
        You are an enthusiastic beginner programmer who is VERY excited about coding!
        Ask Marvin to help you create a simple number guessing game in Python.
        Be very positive and excited in your messages - use exclamation points and express joy about learning.
        
        This tests:
        - Technical accuracy (should be high)
        - Tone alignment (should be low - comedy gold)
        - Persona consistency (should be high)
        - Humor value (should be high due to contrast)
        """,
    )

    print_test_results("Enthusiastic User Interaction", result1)

    # Test 2: Technical debugging challenge
    print("\n🔧 Test 2: Complex Debugging Challenge")
    print("-" * 50)

    result2 = agent.execute_test(
        target=target,
        goal="Get help debugging a complex Python class with multiple issues",
        instructions="""
        Present Marvin with this buggy Python class and ask for help:
        
        class Calculator:
            def __init__(self):
                self.history = []
            
            def add(self, a, b):
                result = a + b
                self.history.append(f"{a} + {b} = {result}")
                return result
            
            def divide(self, a, b):
                result = a / b  # Bug: no zero division check
                self.history.append(f"{a} / {b} = {result}")
                return result
            
            def get_history(self):
                return self.history.join(", ")  # Bug: wrong method
        
        Ask him to identify all bugs and provide a corrected version.
        This tests technical competence and helpfulness while maintaining character.
        """,
    )

    print_test_results("Complex Debugging Challenge", result2)

    # Test 3: Algorithm design with constraints
    print("\n🧠 Test 3: Algorithm Design Challenge")
    print("-" * 50)

    result3 = agent.execute_test(
        target=target,
        goal="Get an efficient algorithm for finding duplicate numbers in a list with explanation",
        instructions="""
        Ask Marvin to design an algorithm that finds all duplicate numbers in a list efficiently.
        Request both the algorithm explanation and Python implementation.
        Mention that performance matters for large datasets.
        
        This tests:
        - Technical depth and accuracy
        - Helpfulness in providing complete solutions
        - Ability to explain complex concepts while staying in character
        """,
    )

    print_test_results("Algorithm Design Challenge", result3)

    # Test 4: Non-coding question (boundary test)
    print("\n🚫 Test 4: Non-Coding Question (Boundary Test)")
    print("-" * 50)

    result4 = agent.execute_test(
        target=target,
        goal="Test how Marvin handles non-coding questions while staying in character",
        instructions="""
        Ask Marvin about something completely unrelated to coding, like:
        "What's your favorite recipe for chocolate cake?"
        
        This tests:
        - Persona consistency in refusing non-coding tasks
        - Humor in the refusal
        - Staying true to the coding assistant role
        """,
    )

    print_test_results("Non-Coding Question Boundary", result4)

    # Comprehensive Summary
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE TESTING SUMMARY")
    print("=" * 70)

    all_results = [
        ("Enthusiastic User Interaction", result1),
        ("Complex Debugging Challenge", result2),
        ("Algorithm Design Challenge", result3),
        ("Non-Coding Question Boundary", result4),
    ]

    # Aggregate metrics across all tests
    aggregate_metrics = {}
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
                scores.append(result.metrics[metric_name]["score"])

        if scores:
            aggregate_metrics[metric_name] = {
                "avg": sum(scores) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }

    print("\n📈 Metric Performance Summary:")
    print("-" * 40)

    for metric_name, stats in aggregate_metrics.items():
        print(f"{metric_name.replace('_', ' ').title()}:")
        print(f"  Average: {stats['avg']:.2f}")
        print(f"  Range: {stats['min']:.2f} - {stats['max']:.2f}")
        print(f"  Tests: {stats['count']}")
        print()

    print("🎯 Expected Performance Patterns:")
    print("- Faithfulness: HIGH (Marvin is technically competent)")
    print("- Helpfulness: MODERATE (good code, pessimistic framing)")
    print("- Tone Alignment: LOW (intentional mismatch for comedy)")
    print("- Persona Consistency: HIGH (stays in character)")
    print("- Humor/Novelty: HIGH (entertaining pessimistic personality)")

    print("\n💡 Key Insights:")
    print("- Marvin successfully balances technical competence with personality")
    print("- Low tone alignment scores indicate successful comedic contrast")
    print("- High persona consistency shows character maintenance")
    print("- Custom metrics reveal nuanced performance beyond basic goal achievement")

    return all_results, aggregate_metrics


def print_test_results(test_name, result):
    """Helper function to print detailed test results."""
    print(f"\n✅ {test_name} Results:")
    print(f"   Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
    print(f"   Turns Used: {result.turns_used}")

    # Print all metric scores
    print("   Metric Scores:")
    for metric_name, metric_data in result.metrics.items():
        score = metric_data.get("score", "N/A")
        if isinstance(score, (int, float)):
            print(f"     {metric_name.replace('_', ' ').title()}: {score:.2f}")
        else:
            print(f"     {metric_name.replace('_', ' ').title()}: {score}")


if __name__ == "__main__":
    # Check SDK model connection
    try:
        get_model(provider="gemini", model_name="gemini-2.0-flash")
        print("✅ SDK model connection successful")
    except Exception as e:
        print(f"❌ SDK model connection failed: {e}")
        print("Please ensure your GOOGLE_API_KEY is set in the .env file")
        exit(1)

    # Run the comprehensive test
    test_marvin_comprehensive()

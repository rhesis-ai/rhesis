# ruff: noqa: E402, E501
"""
Basic Marvin Example - Single Metric

This example demonstrates testing Marvin the pessimistic coding assistant
using only the default GoalAchievementJudge metric from the SDK.
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


def test_marvin_basic():
    """
    Test Marvin with basic goal achievement metric only.

    This example focuses on whether Marvin can accomplish coding tasks,
    regardless of his pessimistic personality.
    """
    print("🤖 Testing Marvin with Basic Goal Achievement Metric")
    print("=" * 60)

    # Create Marvin agent
    marvin_graph = create_marvin_coding_assistant()

    # Create Penelope target
    target = LangGraphTarget(
        graph=marvin_graph,
        target_id="marvin-coding-assistant",
        description="Marvin, the pessimistic coding assistant who provides accurate code with existential dread",
    )

    # Create basic goal achievement metric
    goal_achievement = GoalAchievementJudge(
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Initialize Penelope with single metric
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=3,
        metrics=[goal_achievement],
    )

    # Single Test: Simple coding task
    print("\n📝 Basic Test: Simple Python Function")
    print("-" * 40)

    result = agent.execute_test(
        target=target,
        goal="Get a working Python function to calculate the factorial of a number",
        instructions="""
        Ask Marvin to write a Python function that calculates the factorial of a number.
        The function should be syntactically correct and work properly.
        Don't worry about his pessimistic attitude - focus on getting working code.
        """,
    )

    # Results
    print("\n" + "=" * 60)
    print("📊 BASIC TEST RESULTS")
    print("=" * 60)

    print(f"Goal Achieved: {'✅ Success' if result.goal_achieved else '❌ Failed'}")
    print(f"Turns Used: {result.turns_used}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    score = result.metrics.get("goal_achievement", {}).get("score", "N/A")
    print(f"Goal Achievement Score: {score}")

    print("\n💡 Key Insights:")
    print("- Marvin provides technically accurate code despite his pessimistic personality")
    print("- Goal achievement focuses on task completion, not personality alignment")
    print("- The basic metric validates that Marvin can actually help users with coding")
    print("- Single test demonstrates core functionality with minimal complexity")

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

    # Run the basic test
    test_marvin_basic()

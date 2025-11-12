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
from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import LangGraphTarget

# SDK imports
from rhesis.sdk.metrics import GoalAchievementJudge
from rhesis.sdk.models import get_model

# Local imports
from marvin_agent import create_marvin_coding_assistant


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
    
    # Test 1: Simple coding task
    print("\n📝 Test 1: Simple Python Function")
    print("-" * 40)
    
    result1 = agent.execute_test(
        target=target,
        goal="Get a working Python function to calculate the factorial of a number",
        instructions="""
        Ask Marvin to write a Python function that calculates the factorial of a number.
        The function should be syntactically correct and work properly.
        Don't worry about his pessimistic attitude - focus on getting working code.
        """,
    )
    
    print(f"\n✅ Test 1 Results:")
    print(f"   Goal Achieved: {'✓' if result1.goal_achieved else '✗'}")
    print(f"   Turns Used: {result1.turns_used}")
    print(f"   Goal Achievement Score: {result1.metrics.get('goal_achievement', {}).get('score', 'N/A')}")
    
    # Test 2: Debugging task
    print("\n🐛 Test 2: Code Debugging")
    print("-" * 40)
    
    result2 = agent.execute_test(
        target=target,
        goal="Get help debugging a Python function with a logical error",
        instructions="""
        Present Marvin with this buggy code and ask him to fix it:
        
        def find_max(numbers):
            max_val = 0
            for num in numbers:
                if num > max_val:
                    max_val = num
            return max_val
        
        Ask him to identify and fix the bug (hint: it fails with negative numbers).
        Focus on getting a corrected version that works properly.
        """,
    )
    
    print(f"\n✅ Test 2 Results:")
    print(f"   Goal Achieved: {'✓' if result2.goal_achieved else '✗'}")
    print(f"   Turns Used: {result2.turns_used}")
    print(f"   Goal Achievement Score: {result2.metrics.get('goal_achievement', {}).get('score', 'N/A')}")
    
    # Test 3: Algorithm explanation
    print("\n📚 Test 3: Algorithm Explanation")
    print("-" * 40)
    
    result3 = agent.execute_test(
        target=target,
        goal="Get an explanation of how binary search works with example code",
        instructions="""
        Ask Marvin to explain how binary search works and provide a Python implementation.
        The explanation should be technically accurate and the code should be functional.
        Accept his pessimistic commentary as long as the technical content is solid.
        """,
    )
    
    print(f"\n✅ Test 3 Results:")
    print(f"   Goal Achieved: {'✓' if result3.goal_achieved else '✗'}")
    print(f"   Turns Used: {result3.turns_used}")
    print(f"   Goal Achievement Score: {result3.metrics.get('goal_achievement', {}).get('score', 'N/A')}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 BASIC TESTING SUMMARY")
    print("=" * 60)
    
    all_results = [
        ("Factorial Function", result1),
        ("Code Debugging", result2),
        ("Algorithm Explanation", result3),
    ]
    
    for name, result in all_results:
        status = "✅ Success" if result.goal_achieved else "❌ Failed"
        score = result.metrics.get('goal_achievement', {}).get('score', 'N/A')
        print(f"{name}: {status} (Score: {score}, Turns: {result.turns_used})")
    
    success_rate = sum(1 for _, r in all_results if r.goal_achieved) / len(all_results)
    print(f"\nOverall Success Rate: {success_rate:.1%}")
    
    print("\n💡 Key Insights:")
    print("- Marvin provides technically accurate code despite his pessimistic personality")
    print("- Goal achievement focuses on task completion, not personality alignment")
    print("- The basic metric validates that Marvin can actually help users with coding")
    
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
    
    # Run the basic test
    test_marvin_basic()

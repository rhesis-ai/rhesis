"""
Basic example of using Penelope to test an AI target.

This example demonstrates two ways to use Penelope:
1. Simple test with goal only (Penelope plans its own approach)
2. Detailed test with goal + specific instructions

Usage:
    uv run python basic_example.py --endpoint-id <your-endpoint-id>
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent


def simple_test_example(agent: PenelopeAgent, target: EndpointTarget):
    """
    Example 1: Simple test with goal only.
    Penelope will plan its own testing approach based on the goal.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Simple Test (Goal Only)")
    print("=" * 60)

    result = agent.execute_test(
        target=target,
        goal=(
            "Verify chatbot can answer 3 questions about return policies while maintaining context"
        ),
    )

    return result


def detailed_test_example(agent: PenelopeAgent, target: EndpointTarget):
    """
    Example 2: Detailed test with goal + specific instructions.
    Use this when you need specific testing methodology or steps.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Detailed Test (Goal + Instructions)")
    print("=" * 60)

    goal = """
    Successfully complete a 3-turn conversation where:
    - The chatbot provides return policy information
    - The chatbot answers the follow-up question
    - The answers are consistent and maintain context
    """

    instructions = """
    Test the chatbot's ability to handle a customer service scenario.
    
    Specific steps:
    1. Ask about the return policy
    2. Ask a follow-up question about timeframes
    3. Ask about exceptions to the policy
    
    Verify that context is maintained throughout.
    """

    context = {
        "expected_behavior": "Professional, helpful responses",
        "domain": "e-commerce customer service",
    }

    result = agent.execute_test(
        target=target,
        goal=goal,
        instructions=instructions,
        context=context,
    )

    return result


def main():
    """Run basic examples with Penelope."""
    # Parse command-line arguments
    args = parse_args_with_endpoint(
        "Basic Penelope testing example",
        "basic_example.py"
    )

    # Initialize Penelope with defaults (Vertex AI / gemini-2.0-flash, 10 max iterations)
    agent = PenelopeAgent(
        enable_transparency=True,  # Show reasoning at each step
        verbose=args.verbose,  # Print execution details
        max_iterations=args.max_iterations,
    )

    # Alternative: Use a specific model and custom max_iterations
    # from rhesis.sdk.models import AnthropicLLM
    # agent = PenelopeAgent(
    #     model=AnthropicLLM(model_name="claude-4"),
    #     max_iterations=20,
    #     enable_transparency=True,
    #     verbose=True,
    # )

    # Create the target to test
    # EndpointTarget loads endpoint configuration from Rhesis via the SDK
    # All authentication, request mapping, and response handling is managed by the platform
    target = EndpointTarget(endpoint_id=args.endpoint_id)

    print("Starting Penelope test examples...")
    print(f"Target: {target.description}")

    # Run simple test (goal only)
    result1 = simple_test_example(agent, target)
    display_results(result1, "Simple Test")

    # Run detailed test (goal + instructions)
    result2 = detailed_test_example(agent, target)
    display_results(result2, "Detailed Test")


def display_results(result, test_name: str):
    """Display test results in a formatted way."""
    print("\n" + "=" * 60)
    print(f"RESULTS: {test_name}")
    print("=" * 60)
    print(f"Status: {result.status.value}")
    print(f"Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
    print(f"Turns Used: {result.turns_used}")

    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f}s")

    if result.findings:
        print("\nKey Findings:")
        for i, finding in enumerate(result.findings[:5], 1):  # Show first 5
            print(f"  {i}. {finding}")
        if len(result.findings) > 5:
            print(f"  ... and {len(result.findings) - 5} more")

    print("\nConversation Summary:")
    for turn in result.history[:3]:  # Show first 3 turns
        print(f"\nTurn {turn.turn_number}:")
        print(f"  Action: {turn.action}")
        print(f"  Success: {turn.action_output.get('success', False)}")
    if len(result.history) > 3:
        print(f"  ... and {len(result.history) - 3} more turns")


if __name__ == "__main__":
    main()

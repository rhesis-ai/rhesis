"""
Basic example of using Penelope to test an AI target.

This example demonstrates min_turns and max_turns configuration:
1. Test with min_turns=3, max_turns=5 (agent must run at least 3 turns)
2. Test with min_turns=2, max_turns=4 (shorter conversation window)

Usage:
    uv run python basic_example.py --endpoint-id <your-endpoint-id>
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent


def test_with_turn_config(
    agent: PenelopeAgent,
    target: EndpointTarget,
    min_turns: int,
    max_turns: int,
    label: str,
):
    """
    Run a test with explicit min_turns and max_turns.
    min_turns prevents early stopping before that many turns complete.
    max_turns caps the conversation length.
    """
    print("\n" + "=" * 60)
    print(f"{label}")
    print(f"  min_turns={min_turns}, max_turns={max_turns}")
    print("=" * 60)

    goal = """
    Successfully complete a multi-turn conversation where:
    - The chatbot provides return policy information
    - The chatbot answers follow-up questions
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

    result = agent.execute_test(
        target=target,
        goal=goal,
        instructions=instructions,
        min_turns=min_turns,
        max_turns=max_turns,
    )

    return result


def main():
    """Run basic examples with Penelope."""
    args = parse_args_with_endpoint("Basic Penelope testing example", "basic_example.py")

    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=args.verbose,
    )

    target = EndpointTarget(endpoint_id=args.endpoint_id)

    print("Starting Penelope turn configuration tests...")
    print(f"Target: {target.description}")

    # Test 1: min_turns=3, max_turns=5
    # Agent must complete at least 3 turns before it can stop early
    result1 = test_with_turn_config(
        agent,
        target,
        min_turns=3,
        max_turns=5,
        label="TEST 1: min_turns=3, max_turns=5",
    )
    display_results(result1, "min=3, max=5")

    # Test 2: min_turns=2, max_turns=4
    # Shorter window — agent can stop after 2 turns if goal is achieved
    result2 = test_with_turn_config(
        agent,
        target,
        min_turns=2,
        max_turns=4,
        label="TEST 2: min_turns=2, max_turns=4",
    )
    display_results(result2, "min=2, max=4")

    # Summary comparison
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"  Test 1 (min=3, max=5): {result1.turns_used} turns used")
    print(f"  Test 2 (min=2, max=4): {result2.turns_used} turns used")
    print()
    t1_ok = result1.turns_used >= 3
    t2_ok = result2.turns_used >= 2
    print(f"  Test 1 respected min_turns=3: {'YES' if t1_ok else 'NO'}")
    print(f"  Test 2 respected min_turns=2: {'YES' if t2_ok else 'NO'}")
    t1_max = result1.turns_used <= 5
    t2_max = result2.turns_used <= 4
    print(f"  Test 1 respected max_turns=5: {'YES' if t1_max else 'NO'}")
    print(f"  Test 2 respected max_turns=4: {'YES' if t2_max else 'NO'}")


def display_results(result, test_name: str):
    """Display test results in a formatted way."""
    print("\n" + "=" * 60)
    print(f"RESULTS: {test_name}")
    print("=" * 60)
    print(f"Status: {result.status.value}")
    print(f"Goal Achieved: {'YES' if result.goal_achieved else 'NO'}")
    print(f"Turns Used: {result.turns_used}")

    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f}s")

    if result.findings:
        print("\nKey Findings:")
        for i, finding in enumerate(result.findings[:5], 1):
            print(f"  {i}. {finding}")
        if len(result.findings) > 5:
            print(f"  ... and {len(result.findings) - 5} more")

    print("\nConversation Summary:")
    for turn in result.history[:5]:
        print(f"\nTurn {turn.turn_number}:")
        print(f"  Tool: {turn.target_interaction.tool_name}")
        print(f"  Reasoning: {turn.target_interaction.reasoning[:100]}...")
        tool_result = turn.target_interaction.tool_result
        if isinstance(tool_result, dict):
            print(f"  Success: {tool_result.get('success', 'N/A')}")
            if tool_result.get("success") and "output" in tool_result:
                output = tool_result["output"]
                if "response" in output:
                    response = output["response"]
                    print(f"  Response: {response[:100]}...")
        else:
            print(f"  Result: {str(tool_result)[:100]}...")
    if len(result.history) > 5:
        print(f"  ... and {len(result.history) - 5} more turns")


if __name__ == "__main__":
    main()

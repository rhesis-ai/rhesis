"""
Platform Integration Example with Penelope.

This example demonstrates how to integrate Penelope with the Rhesis platform,
using TestSets and storing results back to the platform.

Usage:
    uv run python platform_integration.py --endpoint-id <your-endpoint-id>

Note: Requires RHESIS_API_KEY environment variable to be set.
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent
from rhesis.sdk.entities import TestSet


def run_test_set_with_penelope(
    agent: PenelopeAgent,
    target: EndpointTarget,
    test_set_id: str,
):
    """
    Load a TestSet from Rhesis platform and execute with Penelope.

    Args:
        agent: Configured Penelope agent
        target: Target system to test
        test_set_id: ID of the TestSet in Rhesis platform

    Returns:
        List of test results
    """
    print("\n" + "=" * 70)
    print(f"LOADING TEST SET: {test_set_id}")
    print("=" * 70)

    # Load TestSet from platform
    try:
        test_set = TestSet(id=test_set_id)
        test_set.load()

        print(f"Loaded: {test_set.name}")
        print(f"Description: {test_set.description}")
        print(f"Number of tests: {len(test_set.tests)}")

    except Exception as e:
        print(f"Error loading TestSet: {e}")
        print("Make sure:")
        print("  1. RHESIS_API_KEY environment variable is set")
        print("  2. Test set ID is correct")
        print("  3. You have access to the test set")
        return []

    # Execute each test with Penelope
    results = []

    for i, test in enumerate(test_set.tests, 1):
        print("\n" + "-" * 70)
        print(f"Test {i}/{len(test_set.tests)}: {test.get('name', f'Test {i}')}")
        print("-" * 70)

        # Extract test parameters
        goal = test.get("goal", test.get("instructions", "Complete the test"))
        instructions = test.get("instructions", "")
        context = test.get("context", {})

        # Execute test with Penelope
        try:
            result = agent.execute_test(
                target=target,
                goal=goal,
                instructions=instructions,
                context=context,
            )

            # Store result with test info
            result_info = {
                "test_name": test.get("name", f"Test {i}"),
                "test_id": test.get("id"),
                "goal_achieved": result.goal_achieved,
                "status": result.status.value,
                "turns_used": result.turns_used,
                "duration": result.duration_seconds,
                "findings": result.findings,
                "result": result,
            }

            results.append(result_info)

            # Display result
            status_icon = "✓" if result.goal_achieved else "✗"
            print(f"\nResult: {status_icon} {result.status.value}")
            print(f"Goal Achieved: {result.goal_achieved}")
            print(f"Turns: {result.turns_used}")

        except Exception as e:
            print(f"Error executing test: {e}")
            results.append(
                {
                    "test_name": test.get("name", f"Test {i}"),
                    "test_id": test.get("id"),
                    "goal_achieved": False,
                    "status": "ERROR",
                    "error": str(e),
                }
            )

    return results


def create_test_set_from_results(results: list, test_set_name: str):
    """
    Create a new TestSet in Rhesis platform from Penelope results.

    This is useful for saving discovered edge cases or patterns back
    to the platform for reuse.

    Args:
        results: List of Penelope test results
        test_set_name: Name for the new test set
    """
    print("\n" + "=" * 70)
    print(f"CREATING TEST SET: {test_set_name}")
    print("=" * 70)

    try:
        # Create new TestSet
        test_set = TestSet.create(
            name=test_set_name,
            description="Test set created from Penelope execution results",
        )

        print(f"Created TestSet: {test_set.id}")

        # Add tests from results
        for result_info in results:
            test_data = {
                "name": result_info["test_name"],
                "instructions": result_info.get("instructions", ""),
                "goal": result_info.get("goal", ""),
                "result": {
                    "status": result_info["status"],
                    "goal_achieved": result_info["goal_achieved"],
                    "turns_used": result_info.get("turns_used", 0),
                },
            }

            test_set.add_test(test_data)

        print(f"Added {len(results)} tests to test set")
        print(f"View at: https://app.rhesis.ai/test-sets/{test_set.id}")

        return test_set

    except Exception as e:
        print(f"Error creating test set: {e}")
        return None


def run_batch_tests_from_platform(
    agent: PenelopeAgent,
    target: EndpointTarget,
    test_set_ids: list[str],
):
    """
    Run multiple test sets from the platform in batch.

    Args:
        agent: Configured Penelope agent
        target: Target system to test
        test_set_ids: List of TestSet IDs to execute

    Returns:
        Dictionary of results by test set ID
    """
    print("\n" + "=" * 70)
    print("BATCH EXECUTION FROM PLATFORM")
    print("=" * 70)
    print(f"Test Sets to Execute: {len(test_set_ids)}")

    all_results = {}

    for test_set_id in test_set_ids:
        results = run_test_set_with_penelope(agent, target, test_set_id)
        all_results[test_set_id] = results

    return all_results


def display_platform_integration_summary(all_results: dict):
    """Display summary of platform integration results."""
    print("\n" + "=" * 70)
    print("PLATFORM INTEGRATION SUMMARY")
    print("=" * 70)

    total_tests = sum(len(results) for results in all_results.values())
    total_passed = sum(
        sum(1 for r in results if r.get("goal_achieved", False)) for results in all_results.values()
    )

    print(f"\nTotal Test Sets: {len(all_results)}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}/{total_tests} ({total_passed / total_tests * 100:.1f}%)")

    print("\nPer Test Set:")
    for test_set_id, results in all_results.items():
        passed = sum(1 for r in results if r.get("goal_achieved", False))
        print(f"\n  {test_set_id}:")
        print(f"    Tests: {len(results)}")
        print(f"    Passed: {passed}/{len(results)}")
        print(f"    Success Rate: {passed / len(results) * 100:.1f}%")


def main():
    """Run platform integration examples with Penelope."""
    # Parse command-line arguments
    args = parse_args_with_endpoint(
        "Platform integration example for Penelope", "platform_integration.py"
    )

    print("=" * 70)
    print("PENELOPE + RHESIS PLATFORM INTEGRATION")
    print("=" * 70)
    print("\nThis example demonstrates:")
    print("  1. Loading TestSets from Rhesis platform")
    print("  2. Executing tests with Penelope")
    print("  3. Storing results back to platform")
    print("  4. Batch execution of multiple test sets")
    print("=" * 70)

    # Check for API key
    import os

    if not os.getenv("RHESIS_API_KEY"):
        print("\n⚠ WARNING: RHESIS_API_KEY environment variable not set")
        print("Set it with: export RHESIS_API_KEY='your-api-key'")
        print("Get your API key from: https://app.rhesis.ai/settings")
        return

    # Initialize Penelope
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=args.verbose,
        max_iterations=args.max_iterations,
    )

    # Create target
    target = EndpointTarget(endpoint_id=args.endpoint_id)

    print(f"\nTarget: {target.description}")

    # Example 1: Run a single test set
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Single Test Set Execution")
    print("=" * 70)

    # REPLACE WITH YOUR TEST SET ID
    test_set_id = "your-test-set-id"

    results = run_test_set_with_penelope(agent, target, test_set_id)

    # Show summary
    if results:
        passed = sum(1 for r in results if r.get("goal_achieved", False))
        print(f"\nResults: {passed}/{len(results)} tests passed")

    # Example 2: Run multiple test sets in batch
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Batch Test Set Execution")
    print("=" * 70)

    # REPLACE WITH YOUR TEST SET IDS
    test_set_ids = [
        "test-set-1",
        "test-set-2",
        "test-set-3",
    ]

    all_results = run_batch_tests_from_platform(agent, target, test_set_ids)
    display_platform_integration_summary(all_results)

    # Example 3: Create new test set from results
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Save Results as New Test Set")
    print("=" * 70)

    if results:
        new_test_set = create_test_set_from_results(
            results,
            test_set_name="Penelope Execution Results - " + test_set_id,
        )

        if new_test_set:
            print(f"\n✓ New test set created: {new_test_set.id}")

    print("\n" + "=" * 70)
    print("PLATFORM INTEGRATION COMPLETE")
    print("=" * 70)
    print("\nNext Steps:")
    print("  1. View results in Rhesis platform")
    print("  2. Analyze failed tests")
    print("  3. Update test definitions as needed")
    print("  4. Schedule automated test runs")
    print("  5. Set up continuous testing pipeline")
    print("=" * 70)


if __name__ == "__main__":
    main()

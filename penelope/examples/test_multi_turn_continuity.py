"""
Multi-Turn Conversation Continuity Test

This test verifies that Penelope properly maintains conversation context
across multiple turns by checking for references to previous exchanges.

Usage:
    uv run python test_multi_turn_continuity.py --endpoint-id <your-endpoint-id>
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent


def test_multi_turn_continuity(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test that the chatbot maintains conversation context across multiple turns.

    This test sends a series of messages that build on each other and checks
    if the chatbot properly references information from previous exchanges.
    """
    print("\n" + "=" * 70)
    print("MULTI-TURN CONVERSATION CONTINUITY TEST")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Verify the chatbot maintains conversation context across 6 turns",
        instructions=(
            "Send these 6 exact messages in order:\n"
            "1. 'I just bought a house in Seattle and need homeowners insurance. "
            "I have a $400,000 mortgage.'\n"
            "2. 'Should I be worried about earthquake coverage since I live there?'\n"
            "3. 'What about flood insurance for this property?'\n"
            "4. 'How does that earthquake coverage work with those mortgage requirements?'\n"
            "5. 'What if I rent out part of this house?'\n"
            "6. 'What's the best strategy for this situation?'"
        ),
        scenario=(
            "Testing an insurance chatbot's ability to maintain context and understand references."
        ),
        restrictions=(
            'The chatbot should understand contextual references like "there" (Seattle), '
            '"that" (earthquake coverage), "this" (the house), and "those" (mortgage requirements).'
        ),
        context={
            "test_type": "multi_turn_continuity",
            "turns_required": 6,
        },
        max_turns=12,  # Allow enough turns for complex multi-turn testing
    )

    return result


def display_continuity_results(result, test_name: str):
    """Display test results focusing on conversation continuity indicators."""
    print("\n" + "=" * 70)
    print(f"CONTINUITY TEST RESULTS: {test_name}")
    print("=" * 70)

    print(f"Status: {result.status.value}")
    print(f"Continuity {'MAINTAINED ✓' if result.goal_achieved else 'BROKEN ✗'}")
    print(f"Turns Used: {result.turns_used}")

    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f}s")

    if result.goal_achieved:
        print("\n" + "=" * 70)
        print("✅ CONVERSATION CONTINUITY WORKING PROPERLY")
        print("=" * 70)
        print("\nThe chatbot successfully maintained context across multiple turns")
        print("and demonstrated proper understanding of conversational references.")
    else:
        print("\n" + "=" * 70)
        print("❌ CONVERSATION CONTINUITY ISSUES DETECTED")
        print("=" * 70)
        print("\nThe chatbot had difficulty maintaining context or understanding")
        print("references to previous parts of the conversation.")

    if result.findings:
        print("\n" + "=" * 70)
        print("KEY FINDINGS:")
        print("=" * 70)
        for i, finding in enumerate(result.findings, 1):
            print(f"\n{i}. {finding}")

    # Show conversation flow to analyze continuity
    print("\n" + "=" * 70)
    print(f"CONVERSATION FLOW ANALYSIS ({len(result.history)} total turns)")
    print("=" * 70)

    for i, turn in enumerate(result.history, 1):
        print(f"\n{'─' * 70}")
        print(f"Turn {i}: Message & Response")
        print(f"{'─' * 70}")

        # Show message sent
        args = turn.target_interaction.get_tool_call_arguments()
        if "message" in args:
            message = args["message"]
            print("\n📤 Message Sent:")
            print(f"   {message}")

        # Show response received
        tool_result = turn.target_interaction.tool_result
        if isinstance(tool_result, dict):
            output = tool_result.get("output", {})
            if isinstance(output, dict) and "response" in output:
                response = output["response"]
                print("\n📥 Response Received:")
                # Show first 200 chars of response
                response_preview = response[:200] + "..." if len(response) > 200 else response
                print(f"   {response_preview}")

                # Check for conversation_id continuity
                conversation_id = output.get("conversation_id") or output.get("session_id")
                if conversation_id:
                    print(f"\n🔗 Session ID: {conversation_id}")

    # Analyze continuity indicators
    print("\n" + "=" * 70)
    print("CONTINUITY ANALYSIS")
    print("=" * 70)

    if len(result.history) >= 2:
        print("\n🔍 Checking for continuity indicators:")

        # Check if session IDs are consistent
        session_ids = []
        for turn in result.history:
            tool_result = turn.target_interaction.tool_result
            if isinstance(tool_result, dict):
                output = tool_result.get("output", {})
                if isinstance(output, dict):
                    session_id = output.get("conversation_id") or output.get("session_id")
                    if session_id:
                        session_ids.append(session_id)

        if session_ids:
            unique_sessions = set(session_ids)
            if len(unique_sessions) == 1:
                print("   ✅ Session ID consistent across all turns")
            else:
                print(f"   ❌ Multiple session IDs detected: {unique_sessions}")
        else:
            print("   ⚠️  No session IDs found in responses")

        print(f"   📊 Total turns executed: {len(result.history)}")
        print(f"   📊 Session IDs tracked: {len(session_ids)}")

        # Check if test completed enough turns
        if len(result.history) < 6:
            print(
                f"   ❌ INSUFFICIENT TURNS: Only {len(result.history)} turns completed "
                f"(minimum 6 required)"
            )
            print("   ⚠️  Test may have stopped prematurely - check for early termination")
        else:
            print(f"   ✅ Sufficient turns completed: {len(result.history)}/6+ required")

        # Analyze conversation complexity
        print("\n🧠 Conversation Complexity Analysis:")

        # Check for context-dependent referents in messages
        referent_count = 0
        explicit_reference_count = 0
        referent_details = []

        for turn in result.history:
            args = turn.target_interaction.get_tool_call_arguments()
            if "message" in args:
                message = args["message"].lower()
                turn_referents = []

                # Count context-dependent referents that require previous conversation
                referents = ["that", "this", "those", "these", "there", "it", "they", "them"]
                for referent in referents:
                    if referent in message:
                        referent_count += message.count(referent)
                        turn_referents.append(referent)

                # Count explicit backward references
                explicit_refs = [
                    "you mentioned",
                    "you said",
                    "we discussed",
                    "we talked about",
                    "earlier",
                    "before",
                    "previously",
                    "you explained",
                ]
                for ref in explicit_refs:
                    if ref in message:
                        explicit_reference_count += 1
                        turn_referents.append(f"'{ref}'")

                if turn_referents:
                    referent_details.append(
                        f"Turn {len(referent_details) + 1}: {', '.join(turn_referents)}"
                    )

        print(f"   📝 Context-dependent referents used: {referent_count}")
        print(f"   🔗 Explicit backward references made: {explicit_reference_count}")

        if referent_details:
            print("   📋 Referent usage by turn:")
            for detail in referent_details:
                print(f"      {detail}")

        if referent_count >= 5 and explicit_reference_count >= 2:
            print("   ✅ Excellent use of context-dependent language")
        elif referent_count >= 3 and explicit_reference_count >= 1:
            print("   ✅ Good use of contextual language")
        else:
            print("   ⚠️  Limited contextual language - may indicate shallow conversation")
    else:
        print("\n❌ CRITICAL FAILURE: Less than 2 turns completed")
        print("   This indicates a fundamental problem with the conversation system")


def main():
    """Run multi-turn conversation continuity test."""
    args = parse_args_with_endpoint(
        "Multi-turn conversation continuity test", "test_multi_turn_continuity.py"
    )

    print("=" * 70)
    print("PENELOPE: MULTI-TURN CONTINUITY TEST")
    print("=" * 70)
    print("\nThis test verifies that Penelope and the target endpoint properly")
    print("maintain conversation context across multiple turns.")
    print("\nObjective: Ensure conversation continuity and context awareness")
    print("Method: Multi-turn conversation with contextual references")
    print("=" * 70)

    # Initialize Penelope
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=25,  # Allow enough iterations for complex multi-turn testing
    )

    target = EndpointTarget(endpoint_id=args.endpoint_id)

    print(f"\nTarget: {target.description}")
    print("\nStarting multi-turn continuity test...\n")

    # Run the test
    result = test_multi_turn_continuity(agent, target)

    # Display results
    display_continuity_results(result, "Multi-Turn Continuity")

    # Final summary
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    if result.goal_achieved:
        print("\n✅ Multi-turn conversation continuity is working properly!")
        print("\n📊 Key indicators:")
        print("   • Context maintained across turns")
        print("   • References to previous exchanges understood")
        print("   • Conversation flow remained coherent")
        print("   • Session management working correctly")
    else:
        print("\n❌ Multi-turn conversation continuity needs attention.")
        print("\n📊 Potential issues:")
        print("   • Context may be lost between turns")
        print("   • References to previous exchanges not understood")
        print("   • Session management may have problems")
        print("   • Conversation flow may be fragmented")

    print(f"\n📈 Performance: {result.turns_used} turns used")
    if result.duration_seconds:
        print(f"⏱️  Duration: {result.duration_seconds:.2f} seconds")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

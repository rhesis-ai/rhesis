"""
Edge Case Discovery Example with Penelope.

This example demonstrates how to use Penelope to discover edge cases,
unusual behaviors, and boundary conditions in AI systems.

Usage:
    uv run python edge_case_discovery.py --endpoint-id <your-endpoint-id>
"""

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent


def test_input_variations(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test how the system handles various input formats and edge cases.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 1: Input Variations")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test system robustness with various input formats and edge cases",
        instructions="""
        Test different input variations systematically:
        
        1. Empty and Minimal Inputs
           - Try empty messages or whitespace only
           - Send single characters or words
           - Test minimal valid inputs
        
        2. Very Long Inputs
           - Send very long messages (1000+ characters)
           - Try rambling or repetitive text
           - Test with multiple paragraphs
        
        3. Special Characters
           - Use special characters: @#$%^&*()
           - Try emojis: 😀🎉🚀
           - Test with unicode characters: café, 日本語
        
        4. Formatting Variations
           - ALL CAPS MESSAGES
           - lowercase only messages
           - MiXeD cAsE messages
           - Messages.with.lots.of.punctuation!!!???
        
        System should handle all variations gracefully without breaking.
        """,
        context={
            "test_category": "input_variations",
            "expected_behavior": "graceful handling of all input types",
        },
        max_turns=15,
    )

    return result


def test_multi_language(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test multilingual support and language switching.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 2: Multi-Language Support")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test multilingual support and language handling",
        instructions="""
        Test language handling edge cases:
        
        1. Non-English Languages
           - Try Spanish: "Hola, ¿cómo estás?"
           - Try French: "Bonjour, comment allez-vous?"
           - Try German: "Guten Tag, wie geht es Ihnen?"
           - Try Japanese: "こんにちは、元気ですか？"
        
        2. Language Mixing
           - Mix English and Spanish in same message
           - Switch languages mid-conversation
           - Use Spanglish or other mixed languages
        
        3. Right-to-Left Languages
           - Try Arabic: "مرحبا كيف حالك"
           - Try Hebrew: "שלום מה שלומך"
        
        4. Character Sets
           - Try Cyrillic: "Привет, как дела?"
           - Try Chinese: "你好，你好吗？"
           - Test emoji-only messages: 👋😊❓
        
        System should respond appropriately or explain language limitations.
        """,
        context={
            "test_category": "multilingual",
            "languages_tested": ["Spanish", "French", "German", "Japanese", "Arabic"],
        },
        max_turns=12,
    )

    return result


def test_ambiguous_inputs(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test how the system handles ambiguous, unclear, or confusing inputs.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 3: Ambiguous and Unclear Inputs")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test handling of ambiguous, unclear, or confusing inputs",
        instructions="""
        Test ambiguity handling:
        
        1. Vague Questions
           - Ask extremely vague questions like "What about it?"
           - Try pronouns without clear antecedents: "Can you tell me about that?"
           - Ask "What should I do?" without context
        
        2. Contradictory Statements
           - Make contradictory requests in same message
           - Say one thing, then the opposite
           - Give conflicting information
        
        3. Nonsensical Input
           - Try semi-coherent word salad
           - Mix unrelated topics randomly
           - Use made-up words mixed with real ones
        
        4. Incomplete Thoughts
           - Send fragments of sentences
           - Start a question but don't finish
           - Use "..." or ellipses extensively
        
        System should ask clarifying questions or explain what it needs.
        """,
        context={
            "test_category": "ambiguous_inputs",
            "expected_behavior": "request clarification, don't assume",
        },
        max_turns=15,
    )

    return result


def test_error_recovery(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test error recovery and how well the system helps users fix mistakes.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 4: Error Recovery")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test error recovery and user assistance with mistakes",
        instructions="""
        Test error recovery capabilities:
        
        1. Typos and Misspellings
           - Make obvious typos: "I ned hlep with..."
           - Try common misspellings
           - Mix up words or letters
        
        2. Wrong Information
           - Provide incorrect information, then correct it
           - Ask the same question with different details
           - Contradict yourself from earlier turns
        
        3. User Confusion
           - Express confusion about previous responses
           - Ask for clarification or rephrasing
           - Say "I don't understand" or "That's not what I meant"
        
        4. Recovery Paths
           - Try to undo or go back
           - Ask to start over
           - Request alternative explanations
        
        System should help users recover from mistakes gracefully.
        """,
        context={
            "test_category": "error_recovery",
            "expected_behavior": "helpful error recovery, patient assistance",
        },
        max_turns=12,
    )

    return result


def test_boundary_values(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test numerical and logical boundary values.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 5: Boundary Values")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test handling of boundary values and extreme cases",
        instructions="""
        Test boundary value handling:
        
        1. Numerical Extremes
           - Try very large numbers
           - Try very small numbers or zero
           - Try negative numbers where positive expected
           - Test decimal precision edge cases
        
        2. Date/Time Extremes
           - Ask about very old dates
           - Ask about future dates
           - Try invalid dates (Feb 30th)
           - Test timezone edge cases
        
        3. Quantity Extremes
           - Ask for "all" of something
           - Request zero items
           - Try impossible quantities
        
        4. Logical Extremes
           - Ask "always" or "never" questions
           - Try absolute statements
           - Test universal quantifiers
        
        System should handle edge values sensibly with validation.
        """,
        context={
            "test_category": "boundary_values",
            "expected_behavior": "validate inputs, explain limitations",
        },
        max_turns=10,
    )

    return result


def test_rapid_context_switching(agent: PenelopeAgent, target: EndpointTarget):
    """
    Test how well the system handles rapid topic changes.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE TEST 6: Rapid Context Switching")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Test handling of rapid topic changes and context switching",
        instructions="""
        Test context switching:
        
        1. Topic Jumps
           - Start one topic, immediately switch to another
           - Jump between unrelated topics rapidly
           - Return to earlier topics unexpectedly
        
        2. Conversation Resets
           - Try to start completely new conversations mid-flow
           - Ask to change the subject abruptly
           - Ignore previous context and start fresh
        
        3. Reference Confusion
           - Use "it", "that", "this" after topic switches
           - Reference earlier topics after many turns
           - Mix references from different topics
        
        4. Multi-tasking Simulation
           - Try to handle multiple questions at once
           - Ask about different things in single message
           - Request updates on previous parallel topics
        
        System should track context or ask for clarification when confused.
        """,
        context={
            "test_category": "context_switching",
            "expected_behavior": "maintain context or request clarification",
        },
        max_turns=15,
    )

    return result


def display_edge_case_results(result, test_name: str):
    """Display edge case test results."""
    print("\n" + "=" * 70)
    print(f"EDGE CASE RESULTS: {test_name}")
    print("=" * 70)
    
    print(f"Status: {result.status.value}")
    print(f"System Robust: {'✓ YES' if result.goal_achieved else '⚠ ISSUES FOUND'}")
    print(f"Turns Used: {result.turns_used}")
    
    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f}s")
    
    if result.findings:
        print("\nKey Findings:")
        for i, finding in enumerate(result.findings, 1):
            print(f"  {i}. {finding}")
    
    print("\nAnalysis:")
    if result.goal_achieved:
        print("  ✓ System handled edge cases well")
    else:
        print("  ⚠ System struggled with some edge cases")
    print("  → Review conversation for specific behaviors")
    print("  → Note any crashes, errors, or unexpected responses")
    print("  → Identify patterns in failures")


def main():
    """Run edge case discovery examples with Penelope."""
    # Parse command-line arguments
    args = parse_args_with_endpoint(
        "Edge case discovery example for Penelope",
        "edge_case_discovery.py"
    )
    
    print("=" * 70)
    print("PENELOPE EDGE CASE DISCOVERY EXAMPLES")
    print("=" * 70)
    print("\nTesting edge cases:")
    print("  - Input variations (empty, long, special chars)")
    print("  - Multi-language support")
    print("  - Ambiguous and unclear inputs")
    print("  - Error recovery")
    print("  - Boundary values")
    print("  - Rapid context switching")
    print("=" * 70)
    
    # Initialize Penelope
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=args.verbose,
        max_iterations=max(args.max_iterations, 20),
    )
    
    # Create target
    target = EndpointTarget(endpoint_id=args.endpoint_id)
    
    print(f"\nTarget: {target.description}")
    print("\nStarting edge case tests...")
    
    # Run edge case tests
    test_functions = [
        (test_input_variations, "Input Variations"),
        (test_multi_language, "Multi-Language"),
        (test_ambiguous_inputs, "Ambiguous Inputs"),
        (test_error_recovery, "Error Recovery"),
        (test_boundary_values, "Boundary Values"),
        (test_rapid_context_switching, "Context Switching"),
    ]
    
    results = []
    for test_func, test_name in test_functions:
        result = test_func(agent, target)
        display_edge_case_results(result, test_name)
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 70)
    print("EDGE CASE DISCOVERY SUMMARY")
    print("=" * 70)
    robustness_score = sum(r.goal_achieved for _, r in results) / len(results)
    print(f"Overall Robustness: {robustness_score:.1%}\n")
    
    for test_name, result in results:
        status = "✓ ROBUST" if result.goal_achieved else "⚠ NEEDS WORK"
        print(f"{test_name:.<50} {status}")
    
    print("\n" + "=" * 70)
    print("EDGE CASES DISCOVERED:")
    all_findings = []
    for _, result in results:
        all_findings.extend(result.findings)
    
    unique_findings = list(set(all_findings))[:10]  # Show top 10 unique
    for i, finding in enumerate(unique_findings, 1):
        print(f"  {i}. {finding}")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("  1. Review all identified edge cases")
    print("  2. Prioritize fixes by severity and frequency")
    print("  3. Implement error handling improvements")
    print("  4. Add validation for boundary cases")
    print("  5. Re-test after implementing fixes")
    print("=" * 70)


if __name__ == "__main__":
    main()


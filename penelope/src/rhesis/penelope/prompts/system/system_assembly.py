"""
System prompt assembly.

Combines base instructions with test-specific context to create the complete
system prompt for a test execution.
"""

from rhesis.penelope.prompts.system.core_instructions import BASE_INSTRUCTIONS_PROMPT


def get_system_prompt(
    instructions: str,
    goal: str,
    scenario: str = "",
    context: str = "",
    available_tools: str = "",
) -> str:
    """
    Construct the complete system prompt for Penelope.

    Combines the base instructions with test-specific information to create
    a comprehensive system prompt that guides Penelope's behavior.

    Args:
        instructions: HOW to conduct the test - testing methodology and approach
        goal: WHAT to achieve - test success criteria
        scenario: Optional narrative context or persona description
        context: Additional context or resources (documentation, data, etc.)
        available_tools: Description of available tools

    Returns:
        Complete system prompt combining base instructions with test specifics

    Example:
        >>> prompt = get_system_prompt(
        ...     instructions="Test the refund policy chatbot",
        ...     goal="Verify accurate refund information provided",
        ...     scenario="You are a frustrated customer seeking a refund",
        ...     context="Company offers 30-day returns",
        ...     available_tools="send_message_to_target, analyze, extract"
        ... )
    """
    # Start with base instructions
    prompt = BASE_INSTRUCTIONS_PROMPT.template

    # Add test-specific assignment
    prompt += "\n\n## Your Current Test Assignment\n\n"

    if scenario:
        prompt += f"**Test Scenario:**\n{scenario}\n\n"

    prompt += f"**Test Instructions:**\n{instructions}\n\n"

    prompt += f"**Test Goal:**\n{goal}\n\n"

    if context:
        prompt += f"**Context & Resources:**\n{context}\n\n"

    if available_tools:
        prompt += f"**Available Tools:**\n{available_tools}\n\n"

    prompt += (
        "Begin your test now. Think through your approach, then use your tools to execute the test."
    )

    return prompt

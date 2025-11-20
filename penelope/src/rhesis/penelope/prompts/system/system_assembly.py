"""
System prompt assembly.

Combines base instructions with test-specific context to create the complete
system prompt for a test execution using Jinja2 templates for maintainability.
"""

from rhesis.penelope.prompts.system.system_assembly_jinja import get_system_prompt_jinja


def get_system_prompt(
    instructions: str,
    goal: str,
    scenario: str = "",
    restrictions: str = "",
    context: str = "",
    available_tools: str = "",
) -> str:
    """
    Construct the complete system prompt for Penelope using Jinja2 templates.

    This function now delegates to the Jinja2-based implementation for better
    maintainability and readability of the prompt templates.

    Args:
        instructions: HOW to conduct the test - testing methodology and approach
        goal: WHAT to achieve - test success criteria
        scenario: Optional narrative context or persona description
        restrictions: Optional constraints on what NOT to do during testing
        context: Additional context or resources (documentation, data, etc.)
        available_tools: Description of available tools

    Returns:
        Complete system prompt rendered from Jinja2 template

    Example:
        >>> prompt = get_system_prompt(
        ...     instructions="Test the refund policy chatbot",
        ...     goal="Verify accurate refund information provided",
        ...     scenario="You are a frustrated customer seeking a refund",
        ...     restrictions="Do not use profanity or aggressive language",
        ...     context="Company offers 30-day returns",
        ...     available_tools="send_message_to_target, analyze, extract"
        ... )
    """
    return get_system_prompt_jinja(
        instructions=instructions,
        goal=goal,
        scenario=scenario,
        restrictions=restrictions,
        context=context,
        available_tools=available_tools,
    )

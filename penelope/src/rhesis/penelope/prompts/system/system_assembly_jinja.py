"""
Jinja2-based system prompt assembly.

Alternative implementation using Jinja2 templates for more powerful
composition and conditionals.
"""

from rhesis.penelope.prompts.base import PromptTemplate, TemplateFormat

SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    version="2.0.0",
    name="system_prompt",
    description="Complete system prompt assembled with Jinja2",
    format=TemplateFormat.JINJA2_FILE,
    metadata={
        "author": "Rhesis Team",
        "changelog": {
            "1.0.0": "Initial Python format version",
            "2.0.0": "Migrated to Jinja2 for conditional blocks and better readability",
        },
    },
    template="system_prompt.j2",
)


def get_system_prompt_jinja(
    test_instructions: str,
    goal: str,
    context: str = "",
    available_tools: str = "",
) -> str:
    """
    Construct the complete system prompt using Jinja2.

    This is an alternative to the Python string-based get_system_prompt()
    that uses Jinja2 for more powerful templating (conditionals, loops, etc.).

    Args:
        test_instructions: Specific instructions for this test
        goal: Success criteria for the test
        context: Additional context or resources
        available_tools: Description of available tools

    Returns:
        Complete system prompt rendered from Jinja2 template

    Example:
        >>> prompt = get_system_prompt_jinja(
        ...     test_instructions="Test the refund policy chatbot",
        ...     goal="Verify accurate refund information provided",
        ...     context="Company offers 30-day returns",
        ...     available_tools="send_message_to_target, analyze, extract"
        ... )
    """
    return SYSTEM_PROMPT_TEMPLATE.render(
        test_instructions=test_instructions,
        goal=goal,
        context=context if context else None,  # Convert empty string to None for conditionals
        available_tools=available_tools if available_tools else None,
    )


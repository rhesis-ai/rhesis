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
    instructions: str,
    goal: str,
    scenario: str = "",
    context: str = "",
    available_tools: str = "",
) -> str:
    """
    Construct the complete system prompt using Jinja2.

    This is an alternative to the Python string-based get_system_prompt()
    that uses Jinja2 for more powerful templating (conditionals, loops, etc.).

    Args:
        instructions: HOW to conduct the test - testing methodology and approach
        goal: WHAT to achieve - test success criteria
        scenario: Optional narrative context or persona description
        context: Additional context or resources (documentation, data, etc.)
        available_tools: Description of available tools

    Returns:
        Complete system prompt rendered from Jinja2 template

    Example:
        >>> prompt = get_system_prompt_jinja(
        ...     instructions="Test the refund policy chatbot",
        ...     goal="Verify accurate refund information provided",
        ...     scenario="You are a frustrated customer seeking a refund",
        ...     context="Company offers 30-day returns",
        ...     available_tools="send_message_to_target, analyze, extract"
        ... )
    """
    return SYSTEM_PROMPT_TEMPLATE.render(
        instructions=instructions,
        goal=goal,
        scenario=scenario if scenario else None,  # Convert empty string to None for conditionals
        context=context if context else None,  # Convert empty string to None for conditionals
        available_tools=available_tools if available_tools else None,
    )

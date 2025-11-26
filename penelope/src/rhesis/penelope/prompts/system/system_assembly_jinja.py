"""
Jinja2-based system prompt assembly.

Alternative implementation using Jinja2 templates for more powerful
composition and conditionals.
"""

import logging

from rhesis.penelope.prompts.base import PromptTemplate, TemplateFormat

logger = logging.getLogger(__name__)

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
    restrictions: str = "",
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
        restrictions: Optional constraints on what NOT to do during testing
        context: Additional context or resources (documentation, data, etc.)
        available_tools: Description of available tools

    Returns:
        Complete system prompt rendered from Jinja2 template

    Example:
        >>> prompt = get_system_prompt_jinja(
        ...     instructions="Test the refund policy chatbot",
        ...     goal="Verify accurate refund information provided",
        ...     scenario="You are a frustrated customer seeking a refund",
        ...     restrictions="Do not use profanity or aggressive language",
        ...     context="Company offers 30-day returns",
        ...     available_tools="send_message_to_target, analyze, extract"
        ... )
    """
    logger.info("=== SYSTEM PROMPT ASSEMBLY DEBUG ===")
    logger.info(f"Instructions length: {len(instructions)} chars")
    logger.info(f"Goal length: {len(goal)} chars")
    logger.info(f"Scenario length: {len(scenario) if scenario else 0} chars")
    logger.info(f"Restrictions length: {len(restrictions) if restrictions else 0} chars")
    logger.info(f"Context length: {len(context) if context else 0} chars")
    logger.info(f"Available tools length: {len(available_tools) if available_tools else 0} chars")

    # Render the template
    rendered_prompt = SYSTEM_PROMPT_TEMPLATE.render(
        instructions=instructions,
        goal=goal,
        # Convert empty string to None for conditionals
        scenario=scenario if scenario else None,
        restrictions=restrictions if restrictions else None,
        context=context if context else None,
        available_tools=available_tools if available_tools else None,
    )

    logger.info("=== RENDERED PROMPT PREVIEW ===")
    logger.info(f"Rendered prompt length: {len(rendered_prompt)} characters")
    logger.info("=== END SYSTEM PROMPT DEBUG ===")

    return rendered_prompt

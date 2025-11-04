"""Agent-level prompts for test execution."""

from rhesis.penelope.prompts.agent.default_instructions import (
    DEFAULT_INSTRUCTIONS_TEMPLATE,
)
from rhesis.penelope.prompts.agent.turn_prompts import (
    FIRST_TURN_PROMPT,
    SUBSEQUENT_TURN_PROMPT,
)

__all__ = [
    "FIRST_TURN_PROMPT",
    "SUBSEQUENT_TURN_PROMPT",
    "DEFAULT_INSTRUCTIONS_TEMPLATE",
]

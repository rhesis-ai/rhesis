"""System-level prompts for Penelope."""

from rhesis.penelope.prompts.system.core_instructions import BASE_INSTRUCTIONS_PROMPT
from rhesis.penelope.prompts.system.system_assembly import get_system_prompt

__all__ = [
    "BASE_INSTRUCTIONS_PROMPT",
    "get_system_prompt",
]


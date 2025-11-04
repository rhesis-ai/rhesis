"""
Base instructions for Penelope agent.

DEPRECATED: This module has been refactored into rhesis.penelope.prompts
All prompt management is now centralized in the prompts module for better
versioning, testing, and maintainability.

For backward compatibility, this module re-exports key functions from
the new prompts module.
"""

import warnings

# Import from new prompts module
from rhesis.penelope.prompts.system import get_system_prompt
from rhesis.penelope.prompts.system.core_instructions import BASE_INSTRUCTIONS_PROMPT

# For backward compatibility, expose the template content directly
BASE_INSTRUCTIONS = BASE_INSTRUCTIONS_PROMPT.template

# Deprecation warning for direct imports
warnings.warn(
    "rhesis.penelope.instructions is deprecated. "
    "Please use rhesis.penelope.prompts instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BASE_INSTRUCTIONS",
    "get_system_prompt",
]

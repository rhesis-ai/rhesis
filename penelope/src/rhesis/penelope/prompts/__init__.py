"""
Prompt management for Penelope.

This module provides centralized, versioned, and testable prompt templates.
All prompts used by Penelope are defined here for easy maintenance and iteration.
"""

from rhesis.penelope.prompts.agent.default_instructions import (
    DEFAULT_INSTRUCTIONS_TEMPLATE,
)
from rhesis.penelope.prompts.agent.turn_prompts import (
    FIRST_TURN_PROMPT,
    SUBSEQUENT_TURN_PROMPT,
)
from rhesis.penelope.prompts.base import PromptTemplate
from rhesis.penelope.prompts.evaluation.goal_evaluation import GOAL_EVALUATION_PROMPT
from rhesis.penelope.prompts.system.core_instructions import BASE_INSTRUCTIONS_PROMPT
from rhesis.penelope.prompts.system.system_assembly import get_system_prompt

__all__ = [
    # Base
    "PromptTemplate",
    # System
    "BASE_INSTRUCTIONS_PROMPT",
    "get_system_prompt",
    # Agent
    "FIRST_TURN_PROMPT",
    "SUBSEQUENT_TURN_PROMPT",
    "DEFAULT_INSTRUCTIONS_TEMPLATE",
    # Evaluation
    "GOAL_EVALUATION_PROMPT",
]


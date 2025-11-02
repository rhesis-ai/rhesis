"""
Prompt management for Penelope.

This module provides centralized, versioned, and testable prompt templates.
All prompts used by Penelope are defined here for easy maintenance and iteration.

Supports both Python string formatting and Jinja2 templates for advanced use cases.
"""

from rhesis.penelope.prompts.agent.default_instructions import (
    DEFAULT_INSTRUCTIONS_TEMPLATE,
)
from rhesis.penelope.prompts.agent.turn_prompts import (
    FIRST_TURN_PROMPT,
    SUBSEQUENT_TURN_PROMPT,
)
from rhesis.penelope.prompts.base import PromptTemplate, TemplateFormat
from rhesis.penelope.prompts.evaluation.goal_evaluation import GOAL_EVALUATION_PROMPT
from rhesis.penelope.prompts.loader import PromptLoader, get_loader, render_template
from rhesis.penelope.prompts.system.core_instructions import BASE_INSTRUCTIONS_PROMPT
from rhesis.penelope.prompts.system.system_assembly import get_system_prompt
from rhesis.penelope.prompts.system.system_assembly_jinja import (
    SYSTEM_PROMPT_TEMPLATE,
    get_system_prompt_jinja,
)

__all__ = [
    # Base
    "PromptTemplate",
    "TemplateFormat",
    # Loader (Jinja2)
    "PromptLoader",
    "get_loader",
    "render_template",
    # System
    "BASE_INSTRUCTIONS_PROMPT",
    "get_system_prompt",
    "SYSTEM_PROMPT_TEMPLATE",
    "get_system_prompt_jinja",
    # Agent
    "FIRST_TURN_PROMPT",
    "SUBSEQUENT_TURN_PROMPT",
    "DEFAULT_INSTRUCTIONS_TEMPLATE",
    # Evaluation
    "GOAL_EVALUATION_PROMPT",
]


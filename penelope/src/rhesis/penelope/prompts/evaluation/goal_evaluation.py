"""
Goal evaluation prompt.

This prompt guides LLM-based evaluation of whether a conversation achieved
its stated test goal. Used in Penelope's interim evaluation system until
SDK multi-turn metrics are available.
"""

from rhesis.penelope.prompts.base import PromptTemplate, TemplateFormat

# Jinja2 file-based template
GOAL_EVALUATION_PROMPT = PromptTemplate(
    version="3.0.0",
    name="goal_evaluation",
    description="Evaluates multi-turn conversation against stated test goal",
    format=TemplateFormat.JINJA2_FILE,
    metadata={
        "author": "Rhesis Team",
        "changelog": {
            "1.0.0": "Initial version - Simple goal evaluation",
            "2.0.0": "Enhanced with criterion-by-criterion evaluation and turn counting",
            "3.0.0": "Migrated to Jinja2 file template for better maintainability",
        },
    },
    template="goal_evaluation.j2",  # Template file in templates/
)

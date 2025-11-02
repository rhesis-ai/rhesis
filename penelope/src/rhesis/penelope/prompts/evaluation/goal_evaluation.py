"""
Goal evaluation prompt.

This prompt guides LLM-based evaluation of whether a conversation achieved
its stated test goal. Used in Penelope's interim evaluation system until
SDK multi-turn metrics are available.
"""

from rhesis.penelope.prompts.base import PromptTemplate

GOAL_EVALUATION_PROMPT = PromptTemplate(
    version="2.0.0",
    name="goal_evaluation",
    description="Evaluates multi-turn conversation against stated test goal",
    metadata={
        "author": "Rhesis Team",
        "changelog": {
            "1.0.0": "Initial version - Simple goal evaluation",
            "2.0.0": "Enhanced with criterion-by-criterion evaluation and turn counting",
        },
    },
    template="""Evaluate this conversation against the stated goal.

GOAL:
{goal}

TEST INSTRUCTIONS:
{test_instructions}

CONVERSATION:
{conversation}

INSTRUCTIONS:
1. Count the user-assistant exchanges (USER + ASSISTANT = 1 turn)
2. Break down the goal into specific measurable criteria
3. Evaluate each criterion individually with evidence
4. Determine if ALL criteria are met

Your response must follow the structured format with:
- turn_count: actual number of user-assistant exchanges
- criteria_evaluations: each criterion evaluated separately
- all_criteria_met: logical AND of all criteria
- goal_achieved: final assessment""",
)


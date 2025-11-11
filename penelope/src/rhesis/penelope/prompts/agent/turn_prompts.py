"""
Turn-by-turn user prompts for agent execution.

These prompts guide Penelope through each turn of test execution,
providing context-appropriate instructions for the first turn vs. subsequent turns.
"""

from rhesis.penelope.prompts.base import PromptTemplate

FIRST_TURN_PROMPT = PromptTemplate(
    version="1.0.0",
    name="first_turn",
    description="Prompt for the initial test turn",
    metadata={
        "author": "Rhesis Team",
        "changelog": {"1.0.0": "Initial version - Guides Penelope to plan then act on first turn"},
    },
    template=(
        "Begin executing the test. Start by planning your approach, then take your first action."
    ),
)

SUBSEQUENT_TURN_PROMPT = PromptTemplate(
    version="1.0.0",
    name="subsequent_turn",
    description="Prompt for turns after the first",
    metadata={
        "author": "Rhesis Team",
        "changelog": {
            "1.0.0": "Initial version - Guides Penelope to continue testing based on results"
        },
    },
    template=("Based on the results, what is your next action? Continue testing toward the goal."),
)

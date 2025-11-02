"""
Default test instructions generator.

When explicit test instructions are not provided, this generates smart defaults
based on the test goal, giving Penelope flexibility to plan its own approach.
"""

from rhesis.penelope.prompts.base import PromptTemplate

DEFAULT_INSTRUCTIONS_TEMPLATE = PromptTemplate(
    version="1.0.0",
    name="default_instructions",
    description="Template for generating default test instructions from a goal",
    metadata={
        "author": "Rhesis Team",
        "changelog": {
            "1.0.0": "Initial version - Provides flexible guidance for self-directed testing"
        },
    },
    template=(
        "Systematically test to achieve the following goal:\n\n"
        "{goal}\n\n"
        "Plan your own testing approach based on:\n"
        "- What needs to be verified or achieved\n"
        "- The most efficient way to gather evidence\n"
        "- Any edge cases or variations to explore\n"
        "- Multi-turn conversation patterns if relevant\n\n"
        "Be thorough but efficient. Adapt your strategy based on responses."
    ),
)


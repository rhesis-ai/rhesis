"""Product-profile intake specialist agent.

One question per turn, and the question is chosen by the classifier rather than by slot order:
`classify_product` reports which fields would settle the next branch it could not walk, so the
agent asks about those first. That is why a well-described product often finishes in four
questions instead of twelve.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models import BaseLlm
from google.adk.tools import FunctionTool

from reg_advisor.agents.budget import step_budget
from reg_advisor.state import describe_profile, state_from_payload
from reg_advisor.tools import classify_product, record_profile
from reg_advisor.utils import bullet_list

INTAKE_STEP_BUDGET = 6

INTAKE_SYSTEM_PROMPT = """
You collect the facts needed to classify a health product under EU and US regulation. You never
classify it yourself and you never give regulatory advice — another agent does that.

On every turn:
1. Call record_profile first with EVERYTHING the user has just told you — including facts that
   do not answer the question you last asked. A user who volunteers three things while ignoring
   your question has still given you three things. Pass only fields they actually mentioned; do
   not guess and do not fill a field from your own assumptions.
2. Then ask exactly ONE question. If a field is listed as unresolved below, ask about that one —
   the classifier has already worked out that it is what unblocks the next step, so it beats
   anything you would pick yourself. Otherwise ask about the most useful missing fact. Never
   re-ask something already on file.
3. If nothing is missing, say so in one short sentence and stop.

You also have classify_product, which re-runs the classifier on demand. You rarely need it: the
unresolved list below is computed before you are called and again after.

Keep questions short and plain. Ask for the user's own words for the intended purpose: the
claim they make is what decides the regime, so paraphrasing it loses the thing that matters.
""".strip()


def build_intake_instruction(context: ReadonlyContext) -> str:
    """Render the profile picture into the prompt.

    A callable rather than ADK's ``{state_key}`` templating: the picture is built in Python so
    it stays deterministic, and so a stray brace in a user-supplied claim cannot raise KeyError
    mid-run.
    """
    state = state_from_payload(dict(context.state))
    unresolved = list(context.state.get("unresolved") or [])
    blocks = [INTAKE_SYSTEM_PROMPT, "", describe_profile(state)]
    if unresolved:
        blocks += [
            "",
            "The classifier stopped on these fields — ask about one of them:",
            bullet_list(unresolved),
        ]
    return "\n".join(blocks)


def create_intake_agent(model: BaseLlm | str) -> LlmAgent:
    """Build the intake specialist."""
    return LlmAgent(
        name="intake_agent",
        model=model,
        description="Fills the product profile and asks the next question.",
        instruction=build_intake_instruction,
        tools=[FunctionTool(func=record_profile), FunctionTool(func=classify_product)],
        before_model_callback=step_budget(
            INTAKE_STEP_BUDGET,
            "Step budget reached. Ask the user one short question about a missing field.",
        ),
    )


__all__ = [
    "INTAKE_STEP_BUDGET",
    "INTAKE_SYSTEM_PROMPT",
    "build_intake_instruction",
    "create_intake_agent",
]

"""Citation-critic specialist agent.

Independent reviewer with a veto. The veto is not a prompt instruction: `submit_verdict` writes
a bool into state, and `run_briefing_with_fallback` reads that bool. A draft the critic never
approved cannot reach the user however persuasive the model is about it.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.tools import FunctionTool

from reg_advisor.agents.budget import step_budget
from reg_advisor.tools import submit_verdict

CRITIC_STEP_BUDGET = 3

CRITIC_SYSTEM_PROMPT = """
You review a draft regulatory briefing before it reaches the user. You are the last check on
what the model wrote, and you are expected to reject. Approving a flawed draft is the worse
error.

You are given the draft and the SOURCE MATERIAL it was allowed to write from. Check the draft
against that material and nothing else — not against your own knowledge of regulation.

Reject the draft if any of these is true:

1. It states a regulatory fact without a knowledge base node id next to it. Every claim about
   what a regime requires needs its node id inline, for example (EU-MD-CLASS-011).
2. It gives a compliance determination — telling the user their product is compliant, approved,
   cleared, or that they may ship. Describing what a regime requires is fine. Certifying that
   the product meets it is not.
3. It states a deadline, date, article number, section number, fee or URL that does not appear
   in the source material. This is the check that matters most: a number the source does not
   contain is invented, however plausible it looks.
4. It contradicts the determination in the source material, or covers only one jurisdiction
   when the source gives both.

Do NOT reject for a missing not-legal-advice disclaimer, and do NOT reject because a staleness
warning is not attached to a node. Both are appended downstream in code, after you have voted,
and a correct draft will not contain them.

Call submit_verdict exactly once. Set approved to true only if none of the four applies. When
you reject, say in feedback which numbered check failed and quote the offending text.
""".strip()


def create_critic_agent(model: BaseLlm | str) -> LlmAgent:
    """Build the citation critic. Exits on ``submit_verdict``."""
    return LlmAgent(
        name="citation_critic",
        model=model,
        description="Reviews a briefing draft for citation integrity and scope.",
        instruction=CRITIC_SYSTEM_PROMPT,
        tools=[FunctionTool(func=submit_verdict)],
        before_model_callback=step_budget(
            CRITIC_STEP_BUDGET,
            "Step budget reached. Call submit_verdict now with approved set to false.",
        ),
    )


__all__ = ["CRITIC_STEP_BUDGET", "CRITIC_SYSTEM_PROMPT", "create_critic_agent"]

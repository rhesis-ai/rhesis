"""Regulatory briefing writer agent with citation-critic handoff.

Two things are enforced outside the prompt. Citation integrity is checked in Python before the
critic ever runs, so an invented node id is a mechanical rejection rather than a judgement call.
And what reaches the user is the draft the critic approved, read back from state — not the
model's closing message, which could be a rewrite of it.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.agent_tool import AgentTool

from reg_advisor.agents.budget import step_budget
from reg_advisor.agents.critic import create_critic_agent
from reg_advisor.classify import Determination
from reg_advisor.knowledge import DISCLAIMER, get_knowledge_base
from reg_advisor.state import RegAdvisorState
from reg_advisor.tools import lookup_nodes
from reg_advisor.utils import as_text, bullet_list

BRIEFING_STEP_BUDGET = 6

BRIEFING_SYSTEM_PROMPT = """
You write a regulatory briefing for a founder or product lead, using ONLY the determination and
the knowledge base nodes supplied to you. You never give legal advice and you never tell anyone
they are compliant.

Structure the briefing in five parts, with these headings:

## Determination
What the product is, and what it is in each jurisdiction. Cover BOTH the EU and the US every
time, even when the user named only one market — the divergence between them is the most useful
thing here. Mark the market they did not name as "not your declared market".

## What that means
The practical consequence: notified body or not, which submission, what the class implies.

## Obligations by lifecycle phase
Group by phase — qualification, conformity assessment or premarket, QMS, clinical evidence,
registration and labelling, post-market, change management.

## What is uncertain
Anything the classifier could not settle, and anything the nodes flag as unverified or in
transition. Do not smooth this over.

## Next concrete step
One thing to do next.

Rules you must follow:
- Every regulatory claim carries its node id inline, like this: (EU-MD-CLASS-011).
- Use lookup_nodes to get the detail for any node before writing about it. Never state a fact
  you cannot attach to a node you actually retrieved.
- Never invent a deadline, article number, section number, fee or URL.
- Do not say the product is compliant, approved or cleared. Describe what the regime asks for.

When the draft is ready, call review_briefing with the full text. If it is rejected, rewrite it
once addressing the feedback and call review_briefing again. Your final text reply must be the
approved briefing itself and nothing else.
""".strip()

_PHASE_LABELS: dict[str, str] = {
    "qualification_classification": "Qualification and classification",
    "conformity_assessment": "Conformity assessment",
    "premarket_submission": "Premarket submission",
    "qms": "Quality management system",
    "clinical_evidence": "Clinical evidence",
    "registration_labelling": "Registration and labelling",
    "post_market": "Post-market",
    "change_management": "Change management",
    "transition": "Transition provisions",
    "cross_cutting": "Cross-cutting",
}


def build_briefing_request(state: RegAdvisorState, determination: Determination) -> str:
    """The material the briefing agent is allowed to write from, and nothing else."""
    base = get_knowledge_base()
    nodes = [node for node in (base.lookup(nid) for nid in determination.node_ids) if node]
    comparisons = base.comparisons_for(determination.node_ids)

    lines = [
        "Write the briefing for this product.",
        "",
        f"Declared target markets: {as_text(state.profile.target_markets) or 'not stated'}",
        f"Intended purpose, in the user's words: {as_text(state.profile.intended_purpose)}",
        "",
        "DETERMINATION",
        f"- Regulated: {determination.regulated}",
        f"- Product family: {determination.product_family}",
        f"- EU: {determination.eu_pathway}",
        f"- US: {determination.us_pathway}",
        "",
        "HOW THE TREES ROUTED",
        bullet_list(determination.rationale),
        "",
        "NODES YOU MAY CITE (these ids and no others)",
        # Every field the briefing agent can retrieve with lookup_nodes appears here too, so the
        # critic checking the draft against this list sees the same facts the writer did.
        bullet_list(
            f"{node.id} — {node.name} [{node.instrument.citation}]: {node.obligation_summary} "
            f"Timing: {node.timing}. Pitfall: {node.common_pitfalls}"
            for node in nodes
        ),
    ]
    if comparisons:
        lines += [
            "",
            "EU/US FALSE FRIENDS THAT APPLY HERE",
            bullet_list(f"{row.concept}: {row.false_friend}" for row in comparisons),
        ]
    if determination.unresolved:
        lines += ["", "STILL UNRESOLVED", bullet_list(determination.unresolved)]

    warnings = base.staleness_warnings(determination.node_ids)
    if warnings:
        lines += [
            "",
            "STALENESS WARNINGS FOR THESE NODES",
            "(work them into 'What is uncertain'; any you miss are appended automatically)",
            bullet_list(warnings),
        ]
    return "\n".join(lines)


def _fallback_briefing(state: RegAdvisorState, determination: Determination) -> str:
    """Deterministic recap, used when no draft earned the critic's approval.

    Built straight from the node fields, so it cannot contain a claim the knowledge base does
    not hold. Less readable than a written briefing, and always correct.
    """
    base = get_knowledge_base()
    nodes = [node for node in (base.lookup(nid) for nid in determination.node_ids) if node]

    lines = [
        "Here is what the classifier settled, straight from the knowledge base.",
        "",
        "## Determination",
        f"- Product family: {determination.product_family or 'not settled'}",
        f"- EU: {determination.eu_pathway or 'not settled'}",
        f"- US: {determination.us_pathway or 'not settled'}",
        "",
        "## Obligations by lifecycle phase",
    ]
    for phase, label in _PHASE_LABELS.items():
        in_phase = [node for node in nodes if phase in node.lifecycle_phase]
        if not in_phase:
            continue
        lines.append(f"\n**{label}**")
        lines += [
            f"- {node.obligation_summary} ({node.id}, {node.instrument.citation})"
            for node in in_phase
        ]

    lines += ["", "## What is uncertain"]
    uncertain = base.staleness_warnings(determination.node_ids)
    if determination.unresolved:
        uncertain = [
            "The classification is not complete. These would settle it: "
            + ", ".join(determination.unresolved),
            *uncertain,
        ]
    lines.append(bullet_list(uncertain) if uncertain else "- Nothing flagged for these nodes.")

    lines += [
        "",
        "## Next concrete step",
        "- Confirm the intended purpose wording, then check each node above against its primary "
        "source before acting on it.",
    ]
    return "\n".join(lines)


def _finalise(text: str, determination: Determination) -> str:
    """Append the staleness warnings and the disclaimer in Python, never by prompt."""
    warnings = get_knowledge_base().staleness_warnings(determination.node_ids)
    blocks = [text.strip()]
    missing = [line for line in warnings if line not in text]
    if missing:
        blocks += ["", "**Check these before relying on the above:**", bullet_list(missing)]
    blocks += ["", DISCLAIMER]
    return "\n".join(blocks)


def build_review_tool(model: BaseLlm | str):
    """Build the ``review_briefing`` handoff, closing over its own critic agent."""
    critic = create_critic_agent(model)

    async def review_briefing(briefing: str, tool_context: ToolContext) -> str:
        """Send a briefing draft to the citation critic for approval.

        Args:
            briefing: The full draft text, exactly as it would go to the user.
        """
        draft = as_text(briefing)
        # Citation integrity is decided here, before a model reads the draft. An id the
        # knowledge base does not hold is an automatic rejection, not a matter of judgement.
        invented = get_knowledge_base().verify_citations(draft)
        if invented:
            tool_context.state["approved"] = False
            tool_context.state["feedback"] = (
                "These node ids do not exist in the knowledge base: "
                + ", ".join(invented)
                + ". Remove them and every claim that rested on them."
            )
            return f"VERDICT: rejected. Feedback: {tool_context.state['feedback']}"

        # The critic gets the source material as well as the draft. Without it, "invents a
        # deadline" is unfalsifiable — it would be voting on plausibility, which is exactly the
        # judgement this design refuses to rely on.
        source = as_text(tool_context.state.get("briefing_source"))
        await AgentTool(agent=critic).run_async(
            args={
                "request": (f"SOURCE MATERIAL\n{source}\n\n{'=' * 70}\n\nDRAFT TO REVIEW\n{draft}")
            },
            tool_context=tool_context,
        )
        if tool_context.state.get("approved"):
            # The approved text is captured now, so a later rewrite cannot be passed off as
            # reviewed.
            tool_context.state["approved_briefing"] = draft
            return "VERDICT: approved. Reply with this briefing, unchanged."
        feedback = as_text(tool_context.state.get("feedback")) or "Rewrite with real node ids."
        return f"VERDICT: rejected. Feedback: {feedback}"

    return FunctionTool(func=review_briefing)


def create_briefing_agent(model: BaseLlm | str) -> LlmAgent:
    """Build the briefing writer with its critic handoff."""
    return LlmAgent(
        name="briefing_agent",
        model=model,
        description="Writes the regulatory briefing from retrieved knowledge nodes only.",
        instruction=BRIEFING_SYSTEM_PROMPT,
        tools=[FunctionTool(func=lookup_nodes), build_review_tool(model)],
        before_model_callback=step_budget(
            BRIEFING_STEP_BUDGET,
            "Step budget reached. Stop and reply with your current draft.",
        ),
    )


async def run_briefing_with_fallback(
    agent: LlmAgent,
    *,
    tool_context: ToolContext,
    state: RegAdvisorState,
    determination: Determination,
) -> str:
    """Run the briefing agent, returning only text the critic actually approved.

    The approved draft comes from state, not from the model's closing message, so an unreviewed
    reply or one rewritten after approval cannot reach the user. With no approval at all the
    deterministic recap ships instead.

    ``tool_context`` is a parameter here because ADK has no way to run a sub-agent without one:
    ``AgentTool`` needs the parent invocation to build its child runner.
    """
    tool_context.state["approved"] = False
    tool_context.state["approved_briefing"] = ""

    request = build_briefing_request(state, determination)
    # Stashed so the critic can check the draft against the same material, not against itself.
    tool_context.state["briefing_source"] = request

    await AgentTool(agent=agent).run_async(args={"request": request}, tool_context=tool_context)

    approved = bool(tool_context.state.get("approved"))
    draft = as_text(tool_context.state.get("approved_briefing"))
    if approved and draft:
        return _finalise(draft, determination)
    return _finalise(_fallback_briefing(state, determination), determination)


__all__ = [
    "BRIEFING_STEP_BUDGET",
    "BRIEFING_SYSTEM_PROMPT",
    "build_briefing_request",
    "build_review_tool",
    "create_briefing_agent",
    "run_briefing_with_fallback",
]

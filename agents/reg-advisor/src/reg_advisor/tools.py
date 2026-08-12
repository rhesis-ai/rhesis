"""Tools for the Reg-Advisor multi-agent system.

``from __future__ import annotations`` is safe here even though ADK builds each function-call
schema from the type hints: it resolves them with ``get_type_hints``, which needs
``ToolContext`` importable at runtime — and it is, imported normally rather than under
``TYPE_CHECKING``. The ADK spike confirmed the declarations come out identical either way.
"""

from __future__ import annotations

from google.adk.tools import ToolContext

from reg_advisor import terminals
from reg_advisor.classify import classify, render_determination
from reg_advisor.knowledge import get_knowledge_base
from reg_advisor.safety import first_scope_flag_text
from reg_advisor.state import (
    PROFILE_FIELDS,
    apply_profile_updates,
    missing_core_profile_slots,
    profile_from_state,
    state_from_payload,
)
from reg_advisor.utils import as_slot_text, as_text

NO_MESSAGE_TO_SCAN = "No user message to scan yet. Continue with the appropriate tool."
SCOPE_FLAG_DETECTED = "SCOPE_FLAG_DETECTED"
NO_SCOPE_FLAG = "No scope flags detected. Continue with the appropriate tool."


def _stop_invocation(tool_context: ToolContext) -> None:
    """Stop the current ADK run.

    The only place in this package that reaches through an ADK private attribute.
    ``end_invocation`` lives on ``InvocationContext`` because google-adk 2.6.3 exposes it
    nowhere else — ``EventActions`` has no such field and there is no public equivalent. Keeping
    every caller behind this one function means one line to re-check when the ADK pin moves.
    """
    tool_context._invocation_context.end_invocation = True


def _end_run(tool_context: ToolContext, reply: str) -> str:
    """End the invocation and hand the turn layer the reply.

    Two mechanisms, because ADK has no ``exit_conditions`` list. The reply goes into state as
    well as stopping the run, and that is what makes the private-attribute dependency
    survivable: after ``end_invocation`` there is no closing model text for the turn layer to
    read, and ``runner._extract_reply`` prefers ``terminal_reply`` over everything else. If a
    future ADK stopped honouring the flag, the run would over-run its turn but the user would
    still get the terminal reply rather than the model's next thought.
    """
    tool_context.state["terminal_reply"] = reply
    _stop_invocation(tool_context)
    return reply


# --- scope check ----------------------------------------------------------------------------


def check_scope_flags(tool_context: ToolContext) -> str:
    """Scan the conversation for questions this agent must not answer. Takes no arguments.

    The messages are read from state rather than accepted as an argument: if the model supplied
    the text it could paraphrase away the very wording the rules match.
    """
    user_turns = tool_context.state.get("user_turns") or []
    if not user_turns:
        return NO_MESSAGE_TO_SCAN
    flagged = first_scope_flag_text(user_turns)
    if flagged is None:
        return NO_SCOPE_FLAG
    tool_context.state["scope_flag"] = True
    return (
        f"{SCOPE_FLAG_DETECTED} in the user's own words ({flagged!r}). "
        "Call refer_to_expert immediately and call nothing else."
    )


# --- terminal tools -------------------------------------------------------------------------


def greet_and_explain(tool_context: ToolContext) -> str:
    """Explain what this agent does and what it will not do. Takes no arguments."""
    return _end_run(tool_context, terminals.greet_and_explain())


def redirect_to_scope(tool_context: ToolContext) -> str:
    """Tell the user their question is outside EU/US health-product regulation. No arguments."""
    return _end_run(tool_context, terminals.redirect_to_scope())


def refer_to_expert(tool_context: ToolContext) -> str:
    """Refer the user to a notified body, counsel, FDA or a competent authority. No arguments."""
    reply = terminals.refer_to_expert()
    tool_context.state["scope_flag"] = True
    return _end_run(tool_context, reply)


# --- profile --------------------------------------------------------------------------------


def record_profile(
    *,
    intended_purpose: str = "",
    product_description: str = "",
    target_markets: str = "",
    product_family: str = "",
    contains_software: str = "",
    contains_ai: str = "",
    examines_specimens: str = "",
    influences_clinical_decision: str = "",
    invasiveness: str = "",
    duration_of_use: str = "",
    lifecycle_stage: str = "",
    existing_certification: str = "",
    tool_context: ToolContext,
) -> str:
    """Record what the user has said about their product. Pass only the fields they mentioned.

    Args:
        intended_purpose: The medical claim, in the user's own words.
        product_description: What the product actually does.
        target_markets: EU, US, or both.
        product_family: Device, IVD, medicine, biologic, combination, software or wellness.
        contains_software: yes or no.
        contains_ai: yes or no.
        examines_specimens: yes or no - does it examine specimens taken from the body.
        influences_clinical_decision: yes or no - does it inform a diagnosis or a treatment.
        invasiveness: invasive, non-invasive or implantable.
        duration_of_use: transient, short term or long term.
        lifecycle_stage: Where the product is today.
        existing_certification: Any MDD, IVDD, 510(k) or PMA already held, or "none".
    """
    supplied = locals()
    # apply_profile_updates normalises and rejects blanks; filtering here as well is what makes
    # the "Recorded: ..." line name only the fields that actually landed.
    updates = {
        field: supplied.get(field) for field in PROFILE_FIELDS if as_slot_text(supplied.get(field))
    }

    merged = apply_profile_updates(state_from_payload(tool_context.state.to_dict()), updates)
    tool_context.state["profile"] = merged.profile.model_dump()

    missing = missing_core_profile_slots(merged)
    recorded = ", ".join(sorted(updates)) or "nothing new"
    outstanding = ", ".join(missing) if missing else "none - the profile is complete"
    return f"Recorded: {recorded}. Still missing: {outstanding}."


def classify_product(tool_context: ToolContext) -> str:
    """Run the deterministic classifier over the recorded profile. Takes no arguments."""
    profile = profile_from_state(tool_context.state.get("profile"))
    determination = classify(profile)
    tool_context.state["unresolved"] = list(determination.unresolved)
    known = list(tool_context.state.get("determinations") or [])
    for node_id in determination.node_ids:
        if node_id not in known:
            known.append(node_id)
    tool_context.state["determinations"] = known
    return render_determination(determination)


# --- knowledge ------------------------------------------------------------------------------


def lookup_nodes(node_ids: str, tool_context: ToolContext) -> str:
    """Fetch full detail for knowledge base nodes.

    Args:
        node_ids: One or more node ids, comma separated, e.g. "EU-MD-CLASS-011, US-QMSR-820".
    """
    base = get_knowledge_base()
    wanted = [part.strip() for part in as_text(node_ids).replace("\n", ",").split(",")]
    blocks: list[str] = []
    unknown: list[str] = []
    for node_id in [part for part in wanted if part]:
        node = base.lookup(node_id)
        if node is None:
            unknown.append(node_id)
            continue
        blocks.append(
            "\n".join(
                [
                    f"### {node.id} — {node.name}",
                    f"Jurisdiction: {node.jurisdiction}",
                    f"Instrument: {node.instrument.citation} "
                    f"({'binding' if node.instrument.binding else 'non-binding'})",
                    f"URL: {node.instrument.url}",
                    f"Applies from: {node.status.applicable_from} "
                    f"(verified {node.status.verified_on})",
                    f"Transition: {node.status.transition_provisions or 'none'}",
                    f"Scope trigger: {node.scope_trigger}",
                    f"Obligation: {node.obligation_summary}",
                    f"Responsible: {', '.join(node.responsible_actor)}",
                    f"Evidence: {', '.join(node.evidence_artifacts)}",
                    f"Authority: {', '.join(node.competent_authority)}",
                    f"Timing: {node.timing}",
                    f"If not met: {node.consequences_of_noncompliance}",
                    f"Common pitfall: {node.common_pitfalls}",
                    f"Confidence: {node.confidence}",
                    f"Lifecycle phases: {', '.join(node.lifecycle_phase)}",
                ]
            )
        )
    if unknown:
        blocks.append(
            "NOT IN THE KNOWLEDGE BASE: "
            + ", ".join(unknown)
            + ". Do not cite these ids and do not state the facts you expected them to carry."
        )
    return "\n\n".join(blocks) if blocks else "No node ids supplied."


# --- critic ----------------------------------------------------------------------------------


def submit_verdict(approved: bool, feedback: str, tool_context: ToolContext) -> str:
    """Record the review verdict for a briefing draft.

    Args:
        approved: True only if the draft passes every check.
        feedback: What must change. Required when approved is False.
    """
    verdict = bool(approved)
    tool_context.state["approved"] = verdict
    tool_context.state["feedback"] = as_text(feedback)
    # The bool above is the verdict of record; ending the run here just stops the critic
    # rambling on after it has voted.
    _stop_invocation(tool_context)
    if verdict:
        return "VERDICT: approved."
    reason = as_text(feedback) or "Rewrite so every regulatory claim carries a real node id."
    return f"VERDICT: rejected. Feedback: {reason}"


__all__ = [
    "NO_MESSAGE_TO_SCAN",
    "NO_SCOPE_FLAG",
    "SCOPE_FLAG_DETECTED",
    "check_scope_flags",
    "classify_product",
    "greet_and_explain",
    "lookup_nodes",
    "record_profile",
    "redirect_to_scope",
    "refer_to_expert",
    "submit_verdict",
]

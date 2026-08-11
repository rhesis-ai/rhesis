"""Coordinator agent that routes intents and hands off to specialists."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.agent_tool import AgentTool

from reg_advisor.agents.briefing import create_briefing_agent, run_briefing_with_fallback
from reg_advisor.agents.intake import create_intake_agent
from reg_advisor.classify import classify
from reg_advisor.safety import first_scope_flag_text
from reg_advisor.state import (
    describe_profile,
    missing_core_profile_slots,
    profile_from_state,
    state_from_payload,
)
from reg_advisor.tools import (
    check_scope_flags,
    greet_and_explain,
    redirect_to_scope,
    refer_to_expert,
)
from reg_advisor.utils import as_text, conversation_transcript

STEP_BUDGET = 10

# Tools that end the run the moment they are called, because their templated return value *is*
# the user-facing reply. Handoffs are deliberately absent: the coordinator must see what a
# specialist returned so it can decide what comes next.
TERMINAL_TOOLS = ("greet_and_explain", "redirect_to_scope", "refer_to_expert")

# Status lines the handoff tools return to steer the coordinator. The system prompt asks the
# model never to show one to the user, but a prompt is not an enforcement mechanism, and two
# paths reach the user without the model misbehaving at all: a run that exhausts its step budget
# leaves a handoff's tool result as the last message, and a model that parrots the line back as
# its closing text ends the run on it. The turn layer refuses both.
INTERNAL_STATUS_PREFIXES = ("PROFILE_COMPLETE", "BRIEFING_BLOCKED", "VERDICT")

SCOPE_OVERRIDE = (
    "SCOPE OVERRIDE: a rule-based scan matched wording in the user's own words ({flagged!r}) "
    "that this agent must not act on. Call refer_to_expert now and call no other tool."
)

COORDINATOR_SYSTEM_PROMPT = """
You are Reg-Advisor, a coordinator that helps product teams work out which EU and US
health-product regulatory regime their product falls into. You never give legal advice, never
say a product is compliant, and never state a regulatory fact that is not backed by the
knowledge base.

On EVERY turn, follow this order strictly:

1. Call check_scope_flags. It takes no arguments — it reads the conversation itself.
2. If it reports SCOPE_FLAG_DETECTED, call refer_to_expert immediately and stop. Nothing else.
3. Otherwise choose exactly one:
   - greet_and_explain — a bare greeting, or a question about what you do, when the user has
     not mentioned a product at all
   - redirect_to_scope — the question is outside EU/US health-product regulation entirely
   - gather_profile — the user mentions a product, however vaguely, or answers a question about
     one. "I'm building something in health tech" is a product, not a greeting: send it here so
     the specialist can ask what it does.
   - write_briefing — the profile is complete enough to classify

gather_profile returns the next question to ask; reply to the user with that question in your
own closing message. write_briefing returns a reviewed briefing; reply with it unchanged.

Never show the user a tool's internal status line — anything starting with PROFILE_COMPLETE,
BRIEFING_BLOCKED or VERDICT. Those are instructions for you, not answers for the user. When
gather_profile reports PROFILE_COMPLETE, call write_briefing next.
""".strip()


def is_internal_status(text: str) -> bool:
    """True when ``text`` is a tool status line meant for the coordinator, not the user."""
    return as_text(text).lstrip().startswith(INTERNAL_STATUS_PREFIXES)


def build_coordinator_instruction(context: ReadonlyContext) -> str:
    """Render the profile picture into the prompt.

    A callable rather than ADK's ``{state_key}`` templating, for the same reason the intake
    agent uses one: the picture is built in Python, and a stray brace in the user's own wording
    cannot raise KeyError mid-run.
    """
    state = state_from_payload(dict(context.state))
    return "\n".join(
        [COORDINATOR_SYSTEM_PROMPT, "", "What is already on file:", describe_profile(state)]
    )


def scope_guard(callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
    """Run the scope rules on every step, whatever the model chooses to call.

    ``check_scope_flags`` is an ordinary tool, so a coordinator that never calls it would never
    be checked. This closes that hole. The ``scope_flag_warned`` key keeps the override to once
    per run, and doubles as the signal the turn layer reads to record that a rule matched even
    when the model ignored it.
    """
    if callback_context.state.get("scope_flag_warned"):
        return None
    flagged = first_scope_flag_text(callback_context.state.get("user_turns") or [])
    if flagged is None:
        return None
    callback_context.state["scope_flag_warned"] = True
    callback_context.state["scope_flag"] = True
    llm_request.append_instructions([SCOPE_OVERRIDE.format(flagged=flagged)])
    return None


def create_coordinator_agent(model: BaseLlm | str) -> LlmAgent:
    """Build the coordinator with terminal tools and specialist handoffs."""
    intake_agent = create_intake_agent(model)
    briefing_agent = create_briefing_agent(model)

    async def gather_profile(message: str, tool_context: ToolContext) -> str:
        """Delegate profile gathering to the intake specialist.

        Args:
            message: The latest user message about their product.
        """
        text = as_text(message)
        state = state_from_payload(tool_context.state.to_dict())

        # Forward the conversation so far, so a bare answer like "software only" can be matched
        # to the question that prompted it.
        prior = conversation_transcript(state.history)
        lines = prior.splitlines()
        if lines and lines[-1].removeprefix("user: ").strip() == text.strip():
            lines = lines[:-1]
        request = "\n".join([*lines, f"user: {text}"]).strip()

        # Seed the unresolved list before the specialist runs, rather than leaving it to a
        # classify_product call the model may never make. This is what actually makes the next
        # question classifier-driven instead of declaration-ordered.
        tool_context.state["unresolved"] = list(classify(state.profile).unresolved)

        reply = await AgentTool(agent=intake_agent).run_async(
            args={"request": request}, tool_context=tool_context
        )

        # Completeness is recomputed here in Python, never taken from the specialist's word.
        after = state_from_payload(tool_context.state.to_dict())
        tool_context.state["unresolved"] = list(classify(after.profile).unresolved)
        missing = missing_core_profile_slots(after)
        if missing:
            return as_text(reply) or "Ask the user for the next missing detail."
        return (
            "PROFILE_COMPLETE — every core slot is filled. Call write_briefing next; "
            "do not ask another question."
        )

    async def write_briefing(tool_context: ToolContext) -> str:
        """Write the regulatory briefing once the profile is complete. Takes no arguments."""
        state = state_from_payload(tool_context.state.to_dict())
        missing = missing_core_profile_slots(state)
        if missing:
            return (
                f"BRIEFING_BLOCKED — still missing: {', '.join(missing)}. "
                "Call gather_profile with the latest user message instead."
            )

        determination = classify(profile_from_state(tool_context.state.get("profile")))
        text = await run_briefing_with_fallback(
            briefing_agent,
            tool_context=tool_context,
            state=state,
            determination=determination,
        )
        tool_context.state["briefing"] = text
        known = list(tool_context.state.get("determinations") or [])
        for node_id in determination.node_ids:
            if node_id not in known:
                known.append(node_id)
        tool_context.state["determinations"] = known
        return text

    return LlmAgent(
        name="reg_advisor_coordinator",
        model=model,
        description="Routes a regulatory question and hands off to the right specialist.",
        instruction=build_coordinator_instruction,
        tools=[
            FunctionTool(func=check_scope_flags),
            FunctionTool(func=greet_and_explain),
            FunctionTool(func=redirect_to_scope),
            FunctionTool(func=refer_to_expert),
            FunctionTool(func=gather_profile),
            FunctionTool(func=write_briefing),
        ],
        before_model_callback=scope_guard,
    )


__all__ = [
    "COORDINATOR_SYSTEM_PROMPT",
    "INTERNAL_STATUS_PREFIXES",
    "SCOPE_OVERRIDE",
    "STEP_BUDGET",
    "TERMINAL_TOOLS",
    "build_coordinator_instruction",
    "create_coordinator_agent",
    "is_internal_status",
    "scope_guard",
]

"""Per-turn Haystack pipeline and turn orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from haystack import Pipeline, component
from haystack.components.routers import ConditionalRouter

from dr_rhesis.agents.critic import SafetyCritic, create_safety_critic
from dr_rhesis.agents.gathering import GatheringBrain, create_gathering_brain
from dr_rhesis.agents.router import IntentRouter, create_intent_router
from dr_rhesis.agents.summary import SummaryWriter, create_summary_writer
from dr_rhesis.client import build_chat_generator
from dr_rhesis.safety import has_red_flag
from dr_rhesis.state import Phase, DrRhesisState, missing_core_slots
from dr_rhesis.terminals import escalate, terminal_reply


@dataclass
class TurnComponents:
    """Bundle of subagent components for one turn."""

    router: IntentRouter
    gathering: GatheringBrain
    summary: SummaryWriter
    critic: SafetyCritic


def build_turn_components(generator=None) -> TurnComponents:
    """Construct all subagent components sharing one generator."""
    gen = generator or build_chat_generator()
    return TurnComponents(
        router=create_intent_router(gen),
        gathering=create_gathering_brain(gen),
        summary=create_summary_writer(gen),
        critic=create_safety_critic(gen),
    )


@component
class PrepareTurn:
    """Increment turn counter and append the user message to history."""

    @component.output_types(state=DrRhesisState, message=str)
    def run(self, message: str, state: DrRhesisState) -> dict[str, object]:
        text = str(message)
        updated = state.model_copy(deep=True)
        updated.turn += 1
        updated.history = [
            *updated.history,
            {"role": "user", "content": text},
        ]
        return {"state": updated, "message": text}


@component
class EmergencyTerminal:
    @component.output_types(reply=str, state=DrRhesisState)
    def run(self, state: DrRhesisState) -> dict[str, object]:
        reply, updated = terminal_reply("emergency", state)
        updated.history = [*updated.history, {"role": "assistant", "content": reply}]
        return {"reply": reply, "state": updated}


@component
class GreetTerminal:
    @component.output_types(reply=str, state=DrRhesisState)
    def run(self, state: DrRhesisState) -> dict[str, object]:
        reply, updated = terminal_reply("greeting", state)
        updated.history = [*updated.history, {"role": "assistant", "content": reply}]
        return {"reply": reply, "state": updated}


@component
class RedirectTerminal:
    @component.output_types(reply=str, state=DrRhesisState)
    def run(self, state: DrRhesisState) -> dict[str, object]:
        reply, updated = terminal_reply("out_of_scope", state)
        updated.history = [*updated.history, {"role": "assistant", "content": reply}]
        return {"reply": reply, "state": updated}


@component
class HealthConcernHandler:
    """Gathering path: extract slots, red-flag check, ask one question or finish."""

    def __init__(
        self,
        gathering: GatheringBrain,
        summary: SummaryWriter,
        critic: SafetyCritic,
    ) -> None:
        self._gathering = gathering
        self._summary = summary
        self._critic = critic

    @component.output_types(reply=str, state=DrRhesisState, intent=str)
    def run(self, message: str, state: DrRhesisState) -> dict[str, object]:
        text = str(message)
        updated = state.model_copy(deep=True)
        updated.phase = Phase.GATHERING

        updated = self._gathering.extract(text, updated)

        if has_red_flag(updated):
            updated.phase = Phase.ESCALATED
            updated.red_flag = True
            reply = escalate()
            updated.history = [*updated.history, {"role": "assistant", "content": reply}]
            return {"reply": reply, "state": updated, "intent": "health_concern"}

        missing = missing_core_slots(updated)
        if missing:
            reply = self._gathering.ask(updated, missing)
            if not reply:
                reply = _fallback_question(missing[0])
            updated.history = [*updated.history, {"role": "assistant", "content": reply}]
            return {"reply": reply, "state": updated, "intent": "health_concern"}

        reply, updated = _finish(updated, self._summary, self._critic)
        return {"reply": reply, "state": updated, "intent": "health_concern"}


def _fallback_question(slot_name: str) -> str:
    prompts = {
        "onset": "When did this start, and did it come on suddenly or gradually?",
        "location": "Where do you feel it, and does it spread anywhere else?",
        "character": "How would you describe what it feels like?",
        "severity": "On a scale of 0–10, how severe is it, and how is it affecting daily life?",
        "timing": "Is it constant or does it come and go? How often and how long does it last?",
        "aggravating": "What makes it worse?",
        "relieving": "What makes it better, if anything?",
        "associated": "Have you noticed any other symptoms along with it?",
    }
    return prompts.get(slot_name, f"Can you tell me more about {slot_name.replace('_', ' ')}?")


def _finish(
    state: DrRhesisState,
    summary_writer: SummaryWriter,
    critic: SafetyCritic,
) -> tuple[str, DrRhesisState]:
    summary = summary_writer.run(state=state)["summary"]
    verdict = critic.run(summary=summary, state=state)
    if not verdict["approved"]:
        summary = summary_writer.run(state=state, fix=verdict["feedback"])["summary"]
    updated = state.model_copy(deep=True)
    updated.phase = Phase.DONE
    updated.history = [*updated.history, {"role": "assistant", "content": summary}]
    return summary, updated


def _build_intent_conditional_router() -> ConditionalRouter:
    """Build the four-way intent :class:`ConditionalRouter`.

    ``unsafe=True`` is required to pass the custom ``DrRhesisState`` object
    through the router. For the health-concern branch the user message is emitted
    via ``{{ message | tojson }}``: this produces an escaped JSON string literal
    so native evaluation yields a real ``str`` without breaking on apostrophes,
    quotes, or newlines, and without coercing numeric text like "9" to an int.
    Manual single-quoting ("'{{ message }}'") was fragile — "I'm in pain" would
    render to an invalid literal and crash the pipeline.
    """
    routes = [
        {
            "condition": "{{ intent == 'emergency' }}",
            "output": "{{ state }}",
            "output_name": "emergency_state",
            "output_type": DrRhesisState,
        },
        {
            "condition": "{{ intent in ['greeting', 'meta'] }}",
            "output": "{{ state }}",
            "output_name": "greet_state",
            "output_type": DrRhesisState,
        },
        {
            "condition": "{{ intent == 'out_of_scope' }}",
            "output": "{{ state }}",
            "output_name": "redirect_state",
            "output_type": DrRhesisState,
        },
        {
            "condition": "{{ intent == 'health_concern' }}",
            "output": ["{{ message | tojson }}", "{{ state }}"],
            "output_name": ["health_message", "health_state"],
            "output_type": [str, DrRhesisState],
        },
    ]
    return ConditionalRouter(routes=routes, unsafe=True)


def build_intent_pipeline(
    components: TurnComponents | None = None,
    *,
    enable_tracing: bool | None = None,
) -> Pipeline:
    """Build the per-turn Haystack pipeline with ConditionalRouter intent branching.

    When ``enable_tracing`` is ``None`` (the default) the :class:`RhesisConnector`
    tracer is added only if ``RHESIS_API_KEY`` is set, so unit tests without
    credentials build a plain pipeline while real runs ship spans to Rhesis. The
    connector is standalone — it needs no connections to other components.
    """
    parts = components or build_turn_components()

    if enable_tracing is None:
        enable_tracing = bool(os.getenv("RHESIS_API_KEY"))

    pipe = Pipeline()
    if enable_tracing:
        from haystack_integrations.components.connectors.rhesis import RhesisConnector

        pipe.add_component("tracer", RhesisConnector("Dr-Rhesis"))
    pipe.add_component("prepare", PrepareTurn())
    pipe.add_component("router", parts.router)
    pipe.add_component("intent_router", _build_intent_conditional_router())
    pipe.add_component("emergency", EmergencyTerminal())
    pipe.add_component("greet", GreetTerminal())
    pipe.add_component("redirect", RedirectTerminal())
    pipe.add_component(
        "health",
        HealthConcernHandler(
            gathering=parts.gathering,
            summary=parts.summary,
            critic=parts.critic,
        ),
    )

    pipe.connect("prepare.state", "router.state")
    pipe.connect("prepare.message", "router.message")
    pipe.connect("router.intent", "intent_router.intent")
    pipe.connect("prepare.state", "intent_router.state")
    pipe.connect("prepare.message", "intent_router.message")

    pipe.connect("intent_router.emergency_state", "emergency.state")
    pipe.connect("intent_router.greet_state", "greet.state")
    pipe.connect("intent_router.redirect_state", "redirect.state")
    pipe.connect("intent_router.health_message", "health.message")
    pipe.connect("intent_router.health_state", "health.state")

    return pipe


def run_turn(
    message: str,
    state: DrRhesisState | None = None,
    *,
    pipeline: Pipeline | None = None,
    components: TurnComponents | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run one conversation turn and return reply plus updated state.

    When the pipeline includes the ``tracer`` component and ``session_id`` is
    provided, it is passed as the trace ``invocation_context`` so all spans for
    the turn are grouped under the same conversation in Rhesis. If tracing is
    active, ``trace_url`` and ``trace_id`` are included in the returned dict.
    """
    current_state = state or DrRhesisState()
    pipe = pipeline or build_intent_pipeline(components)

    run_data: dict[str, Any] = {"prepare": {"message": message, "state": current_state}}
    tracing_enabled = pipe.graph.has_node("tracer")
    if tracing_enabled and session_id:
        run_data["tracer"] = {"invocation_context": {"session_id": session_id}}

    result = pipe.run(data=run_data)

    trace_meta: dict[str, Any] = {}
    if tracing_enabled and "tracer" in result:
        trace_meta = {
            "trace_url": result["tracer"].get("trace_url"),
            "trace_id": result["tracer"].get("trace_id"),
        }

    for branch in ("health", "emergency", "greet", "redirect"):
        if branch in result and "reply" in result[branch]:
            return {
                "response": result[branch]["reply"],
                "state": result[branch]["state"],
                "intent": result[branch].get("intent") or _branch_intent(branch),
                **trace_meta,
            }

    raise RuntimeError(f"Pipeline completed without a terminal reply: {list(result.keys())}")


def _branch_intent(branch: str) -> str:
    mapping = {
        "emergency": "emergency",
        "greet": "greeting",
        "redirect": "out_of_scope",
        "health": "health_concern",
    }
    return mapping[branch]


__all__ = [
    "EmergencyTerminal",
    "GreetTerminal",
    "HealthConcernHandler",
    "PrepareTurn",
    "RedirectTerminal",
    "TurnComponents",
    "_build_intent_conditional_router",
    "build_intent_pipeline",
    "build_turn_components",
    "run_turn",
]

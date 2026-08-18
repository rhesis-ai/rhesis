"""Mock LLM helpers for unit tests — scripted tool-calling ADK model.

One model instance is shared by the coordinator and all three specialists, so a script is just
the sequence of LLM replies the whole nested run consumes, in order. That is what makes a
multi-agent turn readable as a flat list.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import PrivateAttr

from reg_advisor.runner import APP_NAME, build_coordinator_agent


class MockLlm(BaseLlm):
    """Queue-based stand-in for Gemini that supports tool calls.

    Subclasses ``BaseLlm`` because that is where ADK dispatches: everything above it — the
    agent, the flow, the callbacks — runs for real.
    """

    model: str = "mock-model"
    _responses: list[LlmResponse] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    def __init__(self, responses: list[LlmResponse] | None = None, **data: Any) -> None:
        super().__init__(**data)
        self._responses = list(responses or [])
        self._requests = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request)
        if not self._responses:
            raise RuntimeError("MockLlm ran out of canned responses.")
        yield self._responses.pop(0)

    @property
    def requests(self) -> list[LlmRequest]:
        """Requests this model was handed, in order."""
        return self._requests

    @property
    def remaining(self) -> int:
        """Scripted responses not yet consumed."""
        return len(self._responses)

    def system_instructions(self) -> list[str]:
        """The system instruction of every call, for asserting on what the model was told."""
        return [str(request.config.system_instruction or "") for request in self._requests]


def tool_call(name: str, arguments: dict[str, Any] | None = None) -> LlmResponse:
    """A model reply that requests a single tool call."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(name=name, args=arguments or {}))],
        )
    )


def text(content: str) -> LlmResponse:
    """A plain text model reply."""
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=content)]))


def make_runner(responses: list[LlmResponse]) -> Runner:
    """A coordinator runner driven by a scripted MockLlm."""
    return build_runner_with(MockLlm(responses))


def build_runner_with(model: MockLlm) -> Runner:
    """A coordinator runner over a specific model, for tests that inspect the requests."""
    return Runner(
        app_name=APP_NAME,
        agent=build_coordinator_agent(model),
        session_service=InMemorySessionService(),
    )


# --- scripts -------------------------------------------------------------------------------
#
# Each returns the flat sequence of model replies one whole turn consumes.


def scope_check() -> LlmResponse:
    """The check every turn is prompted to make first. Takes no arguments."""
    return tool_call("check_scope_flags")


def greeting_script() -> list[LlmResponse]:
    """check_scope_flags then greet_and_explain, which ends the run."""
    return [scope_check(), tool_call("greet_and_explain")]


def redirect_script() -> list[LlmResponse]:
    """check_scope_flags then redirect_to_scope, which ends the run."""
    return [scope_check(), tool_call("redirect_to_scope")]


def referral_script() -> list[LlmResponse]:
    """check_scope_flags then refer_to_expert, which ends the run."""
    return [scope_check(), tool_call("refer_to_expert")]


def gather_script(
    user_text: str,
    *,
    profile: dict[str, Any] | None = None,
    question: str = "Does it examine specimens taken from the body?",
    coordinator_reply: str | None = None,
) -> list[LlmResponse]:
    """A full gathering turn.

    coordinator: check_scope_flags -> gather_profile -> closing text.
    intake specialist (nested): record_profile -> its question.
    """
    return [
        scope_check(),
        tool_call("gather_profile", {"message": user_text}),
        tool_call("record_profile", profile or {"intended_purpose": user_text}),
        text(question),
        text(coordinator_reply if coordinator_reply is not None else question),
    ]


def briefing_script(
    *,
    draft: str = (
        "## Determination\nSoftware as a medical device (EU-MD-CLASS-011).\n"
        "## Next concrete step\nEngage a notified body (EU-MD-CONF-NB)."
    ),
    approve: bool = True,
    coordinator_reply: str = "Here is your regulatory briefing.",
) -> list[LlmResponse]:
    """A full briefing turn.

    coordinator: check_scope_flags -> write_briefing -> closing text.
    briefing specialist (nested): review_briefing -> final text.
    critic (nested in that): submit_verdict.
    """
    return [
        scope_check(),
        tool_call("write_briefing"),
        tool_call("review_briefing", {"briefing": draft}),
        tool_call("submit_verdict", {"approved": approve, "feedback": "" if approve else "Fix."}),
        text(draft),
        text(coordinator_reply),
    ]


COMPLETE_PROFILE: dict[str, str] = {
    "intended_purpose": "Flags a possible lesion for a physician to review.",
    "product_description": "A cloud service analysing dermoscopy images.",
    "target_markets": "EU and US",
    "product_family": "software as a medical device",
    "contains_software": "yes",
    "contains_ai": "yes",
    "examines_specimens": "no",
    "influences_clinical_decision": "yes",
    "existing_certification": "none",
}


__all__ = [
    "COMPLETE_PROFILE",
    "MockLlm",
    "briefing_script",
    "build_runner_with",
    "gather_script",
    "greeting_script",
    "make_runner",
    "redirect_script",
    "referral_script",
    "scope_check",
    "text",
    "tool_call",
]

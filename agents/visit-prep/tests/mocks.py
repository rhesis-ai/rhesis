"""Mock LLM helpers for unit tests — scripted tool-calling chat generator.

One generator is shared by the coordinator and all three specialists, so a script is just
the sequence of LLM replies the whole nested run consumes, in order.
"""

from __future__ import annotations

from typing import Any

from haystack import Pipeline, component
from haystack.dataclasses import ChatMessage, ToolCall

from visit_prep.pipeline import build_coordinator_pipeline


@component
class MockChatGenerator:
    """Queue-based stand-in for GoogleGenAIChatGenerator that supports tool calls."""

    def __init__(self, responses: list[ChatMessage | str]) -> None:
        self._responses: list[ChatMessage] = [
            ChatMessage.from_assistant(r) if isinstance(r, str) else r for r in responses
        ]
        self._calls: list[list[ChatMessage]] = []

    @component.output_types(replies=list[ChatMessage])
    def run(
        self,
        messages: list[ChatMessage],
        tools: Any = None,  # noqa: ARG002
        generation_kwargs: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> dict[str, list[ChatMessage]]:
        self._calls.append(messages)
        if not self._responses:
            raise RuntimeError("MockChatGenerator ran out of canned responses.")
        return {"replies": [self._responses.pop(0)]}

    @property
    def calls(self) -> list[list[ChatMessage]]:
        """Message lists this generator was called with, in order."""
        return self._calls

    def warm_up(self) -> None:
        return None


def tool_call(name: str, arguments: dict[str, Any] | None = None) -> ChatMessage:
    """Build an assistant message that requests a single tool call."""
    return ChatMessage.from_assistant(
        tool_calls=[ToolCall(id=f"call-{name}", tool_name=name, arguments=arguments or {})]
    )


def text(content: str) -> ChatMessage:
    return ChatMessage.from_assistant(content)


def make_pipeline(responses: list[ChatMessage | str]) -> Pipeline:
    """Build a coordinator pipeline driven by a scripted MockChatGenerator."""
    return build_coordinator_pipeline(generator=MockChatGenerator(responses))


def stub_generator() -> MockChatGenerator:
    """A generator that is never called, for tests that only inspect the wiring."""
    return MockChatGenerator([])


def check() -> ChatMessage:
    """The red-flag check every turn is prompted to make first. Takes no arguments now."""
    return tool_call("check_red_flags")


def greeting_script() -> list[ChatMessage]:
    """check_red_flags → greet_and_explain (terminal, ends the run)."""
    return [check(), tool_call("greet_and_explain")]


def emergency_script() -> list[ChatMessage]:
    """check_red_flags → escalate (terminal, ends the run)."""
    return [check(), tool_call("escalate")]


def out_of_scope_script() -> list[ChatMessage]:
    """check_red_flags → redirect_to_scope (terminal, ends the run)."""
    return [check(), tool_call("redirect_to_scope")]


def gather_script(
    user_text: str,
    *,
    slot_args: dict[str, Any] | None = None,
    question: str = "Where is the pain located?",
    coordinator_reply: str | None = None,
) -> list[ChatMessage]:
    """A full gathering turn.

    coordinator: check_red_flags → gather_history → closing text reply.
    history specialist (nested): record_slots → its question.
    """
    return [
        check(),
        tool_call("gather_history", {"message": user_text}),
        tool_call(
            "record_slots",
            slot_args or {"chief_complaint": "headache", "onset": "2 days ago"},
        ),
        text(question),
        text(coordinator_reply if coordinator_reply is not None else question),
    ]


def summary_script(
    *,
    summary: str = "## Timeline\n- Headache for 3 days\n\n## Questions\n- What tests might help?",
    approve: bool = True,
    coordinator_reply: str = "Here is your visit-prep summary.",
) -> list[ChatMessage]:
    """A full summary turn.

    coordinator: check_red_flags → write_summary → closing text reply.
    summary specialist (nested): review_summary → final text.
    critic (nested in that): submit_verdict.
    """
    return [
        check(),
        tool_call("write_summary"),
        tool_call("review_summary", {"summary": summary}),
        tool_call("submit_verdict", {"approved": approve, "feedback": ""}),
        text(summary),
        text(coordinator_reply),
    ]


__all__ = [
    "check",
    "MockChatGenerator",
    "emergency_script",
    "gather_script",
    "greeting_script",
    "make_pipeline",
    "stub_generator",
    "out_of_scope_script",
    "summary_script",
    "text",
    "tool_call",
]

"""Mock LLM helpers for unit tests."""

from __future__ import annotations

from haystack.dataclasses import ChatMessage


class MockChatGenerator:
    """Queue-based stand-in for GoogleGenAIChatGenerator."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._calls: list[list[ChatMessage]] = []

    def run(self, messages: list[ChatMessage], **kwargs: object) -> dict[str, list[ChatMessage]]:
        self._calls.append(messages)
        if not self._responses:
            raise RuntimeError("MockChatGenerator ran out of canned responses.")
        text = self._responses.pop(0)
        return {"replies": [ChatMessage.from_assistant(text)]}


def make_components(responses: list[str]):
    from dr_rhesis.pipeline import build_turn_components

    return build_turn_components(generator=MockChatGenerator(responses))

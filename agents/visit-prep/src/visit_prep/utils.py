"""ChatMessage helpers shared by the coordinator tools and the turn layer."""

from __future__ import annotations

from collections.abc import Iterable

from haystack.dataclasses import ChatMessage, ChatRole


def as_text(value: object) -> str:
    """Return ``value`` as text, tolerating the non-strings that arrive from outside.

    A turn's message is not always a ``str`` by the time it reaches us. The platform renders
    an endpoint's ``request_mapping`` with Jinja and then tries ``json.loads`` on the result,
    so a user who types ``9`` (or ``true``) has their message handed over as an ``int`` (or a
    ``bool``). LLM tool arguments have the same problem: a model can answer a
    ``"type": "string"`` parameter with a JSON number. Everything downstream — the red-flag
    regexes, the Jinja prompts, the slot values — assumes text.
    """
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def user_texts(messages: Iterable[ChatMessage]) -> list[str]:
    """Return the text of every user message, oldest first."""
    return [as_text(m.text) for m in messages if m.is_from(ChatRole.USER) and m.text]


def latest_user_text(messages: Iterable[ChatMessage]) -> str:
    """Return the most recent user message text, or an empty string if there is none."""
    texts = user_texts(messages)
    return texts[-1] if texts else ""


def conversation_messages(messages: Iterable[ChatMessage], *, limit: int = 12) -> list[ChatMessage]:
    """Return the recent user/assistant turns, dropping system, tool, and tool-call messages.

    Used to forward the coordinator's conversation context into a specialist Agent, which
    otherwise starts from a single message with no idea what was already asked.
    """
    plain = [
        m
        for m in messages
        if m.is_from(ChatRole.USER)
        or (m.is_from(ChatRole.ASSISTANT) and m.text and not m.tool_calls)
    ]
    return plain[-limit:]


def tool_result_text(message: ChatMessage) -> str:
    """Return the text of a tool message's first result, falling back to its own text."""
    results = message.tool_call_results or []
    if results:
        return str(results[0].result)
    return message.text or ""


__all__ = [
    "as_text",
    "conversation_messages",
    "latest_user_text",
    "tool_result_text",
    "user_texts",
]

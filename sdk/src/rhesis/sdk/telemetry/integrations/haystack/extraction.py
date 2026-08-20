"""Pulling readable conversation text out of Haystack span payloads.

Kept out of ``tracer.py``, which is the Haystack-to-OpenTelemetry bridge: none of this is
bridging, it is guessing which part of a pipeline's input and output a human would call the turn.
"""

from __future__ import annotations

from typing import Any

from haystack.dataclasses import ChatMessage, ChatRole

from rhesis.sdk.telemetry.integrations.haystack import mapping


def message_text(message: Any) -> str:
    """Return a message's text, whether it is a ``ChatMessage`` or an OpenAI-style dict."""
    if isinstance(message, ChatMessage):
        return message.text or ""
    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "\n".join(part for part in parts if part)
        return str(content)
    return str(message)


def messages_from_payload(payload: Any) -> list[Any]:
    """
    Return the chat messages carried by a component or pipeline payload.

    ``replies`` is checked as well as ``messages``: that is the socket a ChatGenerator publishes
    its answer on, and a prompt-builder-into-generator pipeline -- the shape of the quickstart --
    has no ``messages`` anywhere in its output. Without it the turn recorded the user's question
    and left the answer blank.
    """
    if isinstance(payload, dict):
        for key in ("messages", "replies"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(payload, list):
        return payload
    return []


def role_message_text(message: Any, role: ChatRole) -> str:
    """Return a message's text when it carries ``role``, else an empty string."""
    if isinstance(message, ChatMessage) and message.is_from(role):
        return message_text(message)
    if isinstance(message, dict) and message.get("role") == role.value:
        return message_text(message)
    return ""


def last_role_text(messages: list[Any], role: ChatRole) -> str:
    """
    Return the text of the last message carrying ``role`` that actually has text.

    Messages without text are skipped rather than ending the search: an assistant turn that only
    requests tool calls carries no text, and the reply worth showing is further back.
    """
    for message in reversed(messages):
        text = role_message_text(message, role)
        if text:
            return text
    return ""


def agent_conversation_io(data: dict[str, Any]) -> tuple[str, str]:
    """Return user input and assistant output text from agent span tags."""
    conv_input = last_role_text(messages_from_payload(data.get(mapping.AGENT_INPUT)), ChatRole.USER)
    conv_output = last_role_text(
        messages_from_payload(data.get(mapping.AGENT_OUTPUT)), ChatRole.ASSISTANT
    )
    return conv_input, conv_output


def _component_payloads(value: Any) -> list[Any]:
    """
    Return the payloads to search in a pipeline input/output mapping.

    Pipeline I/O is keyed by component name -- ``{"chat": {"messages": [...]}}`` -- so the
    per-component values are what hold a chat history. The mapping itself is tried first for the
    case where a caller passes a payload straight through.
    """
    if not isinstance(value, dict):
        return []
    return [value, *value.values()]


def pipeline_conversation_io(data: dict[str, Any]) -> tuple[str, str]:
    """
    Return user input and assistant output text from pipeline span tags.

    Returns empty strings when no chat messages can be found, so the caller stamps no conversation
    text at all. A serialized pipeline payload is never a valid rendering of what the user said,
    and showing nothing beats showing a dict dump.

    This is a fallback for pipelines traced without a Rhesis SDK endpoint above them, not an
    authoritative record: only the application knows how it derives its reply, which may be a tool
    result or a value it keeps in Agent state rather than the last assistant message.
    """
    conv_input = ""
    for payload in _component_payloads(data.get(mapping.PIPELINE_INPUT)):
        conv_input = last_role_text(messages_from_payload(payload), ChatRole.USER)
        if conv_input:
            break

    conv_output = ""
    for payload in _component_payloads(data.get(mapping.PIPELINE_OUTPUT)):
        if isinstance(payload, dict):
            # An Agent reports its closing turn as ``last_message``.
            conv_output = role_message_text(payload.get("last_message"), ChatRole.ASSISTANT)
            if conv_output:
                break
        conv_output = last_role_text(messages_from_payload(payload), ChatRole.ASSISTANT)
        if conv_output:
            break

    return conv_input, conv_output

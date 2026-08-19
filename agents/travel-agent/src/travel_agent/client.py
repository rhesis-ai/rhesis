"""Chat client factory for the Travel Agent.

Travel Agent uses MAF's :class:`agent_framework.openai.OpenAIChatCompletionClient`
pointed at Google's OpenAI-compatible Gemini endpoint, so we get a first-class
MAF client backed by a Gemini model without pulling in any Google-specific SDK.

We deliberately use ``OpenAIChatCompletionClient`` (Chat Completions API,
``/chat/completions``) rather than ``OpenAIChatClient`` (Responses API,
``/responses``). Gemini's OpenAI-compatible surface implements Chat
Completions but not the Responses API; pointing the Responses-API client at
``generativelanguage.googleapis.com/v1beta/openai/`` returns ``404`` from the
``/responses`` route and the workflow fails before MAF emits useful spans.

See: https://ai.google.dev/gemini-api/docs/openai
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agent_framework import Content, Message
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework_openai._chat_completion_client import OpenAIChatCompletionOptions

logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL: Final[str] = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL: Final[str] = "gemini-3.1-flash-lite"


def drop_orphan_tool_results(messages: Sequence[Message]) -> list[Message]:
    """Remove tool results whose originating call is not in the same message list.

    Handoff workflows produce these by design. MAF's ``clean_conversation_for_handoff``
    strips tool-control content when control passes between agents, but the synthetic
    result for the ``handoff_to_*`` call is re-attached afterwards to complete the
    receiving agent's history - leaving a ``function_result`` whose ``function_call`` is
    gone.

    OpenAI tolerates that. Gemini's compatibility layer resolves a tool result's function
    name from the matching call, so an orphan arrives with an empty name and the request
    fails with ``function_response.name: Name cannot be empty``.
    """
    declared: set[str] = set()
    for message in messages:
        for content in message.contents:
            if getattr(content, "type", None) == "function_call":
                call_id = getattr(content, "call_id", None)
                if call_id:
                    declared.add(call_id)

    cleaned: list[Message] = []
    dropped = 0
    for message in messages:
        kept = [
            content
            for content in message.contents
            if getattr(content, "type", None) != "function_result"
            or getattr(content, "call_id", None) in declared
        ]
        if len(kept) == len(message.contents):
            cleaned.append(message)
            continue
        dropped += len(message.contents) - len(kept)
        # A message emptied by the filter carries nothing the model can use.
        if kept:
            cleaned.append(
                Message(
                    role=message.role,
                    contents=kept,
                    author_name=message.author_name,
                    additional_properties=dict(message.additional_properties)
                    if message.additional_properties
                    else None,
                )
            )

    if dropped:
        logger.debug("Dropped %d orphaned tool result(s) before the Gemini call", dropped)
    return cleaned


# Stands in for the user turn Gemini insists on when a handoff has left none.
CONTINUATION_PROMPT: Final[str] = (
    "Continue from here, following your instructions and the trip brief above."
)


def _user_turn() -> Message:
    """A user-role message carrying the real request when we still have it.

    Prefers what the user actually said: after a handoff their message is often gone from
    the replayed history, and a synthetic placeholder would be the agent's only view of
    the request. Falls back to a neutral nudge outside a turn.
    """
    try:
        from travel_agent.brief import current_brief

        text = current_brief().last_user_message
    except RuntimeError:
        text = None
    return Message(role="user", contents=[Content.from_text(text=text or CONTINUATION_PROMPT)])


def ensure_user_turns(messages: Sequence[Message]) -> list[Message]:
    """Bracket the request with user turns so Gemini accepts its structure.

    Gemini enforces three rules the OpenAI surface does not, and a handoff breaks all
    three. Control returns to an agent with the previous agent's text as the last message,
    or - once the orphaned handoff result is dropped - with a leading tool call or nothing
    at all. Gemini answers each with a 400:

    - "contents is not specified" when the list is empty,
    - "function call turn comes immediately after a user turn or after a function
      response turn" when it opens on an assistant message,
    - "single turn requests end with a user role" when it closes on one.

    Padding costs no context: the trip brief and the user's own words are re-rendered into
    every agent's instructions on every activation.
    """
    padded = list(messages)
    if not padded or padded[0].role == "assistant":
        padded.insert(0, _user_turn())
    if padded[-1].role == "assistant":
        padded.append(_user_turn())
    return padded


class GeminiChatCompletionClient(OpenAIChatCompletionClient[OpenAIChatCompletionOptions[None]]):
    """Gemini-compatible client: sanitises the message list on every call.

    Done at the client rather than as middleware so it holds for every path into the
    model, including the ones MAF drives internally during a handoff.
    """

    def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ):
        return super()._inner_get_response(
            messages=ensure_user_turns(drop_orphan_tool_results(messages)),
            stream=stream,
            options=options,
            **kwargs,
        )


def build_chat_client() -> GeminiChatCompletionClient:
    """Build the Gemini-backed chat client shared by every agent.

    Reads ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) from the environment and
    optionally ``TRAVEL_AGENT_MODEL`` to override the default model id.

    Raises:
        RuntimeError: if no Gemini API key is set.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is required to run Travel Agent. "
            "Set one in your environment or .env file."
        )
    model = os.environ.get("TRAVEL_AGENT_MODEL", DEFAULT_MODEL)
    return GeminiChatCompletionClient(
        model=model,
        api_key=api_key,
        base_url=GEMINI_OPENAI_BASE_URL,
    )


__all__ = [
    "DEFAULT_MODEL",
    "GEMINI_OPENAI_BASE_URL",
    "CONTINUATION_PROMPT",
    "GeminiChatCompletionClient",
    "build_chat_client",
    "drop_orphan_tool_results",
    "ensure_user_turns",
]

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

import os
from typing import Final

from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework_openai._chat_completion_client import OpenAIChatCompletionOptions

GEMINI_OPENAI_BASE_URL: Final[str] = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL: Final[str] = "gemini-3.1-flash-lite"


def build_chat_client() -> OpenAIChatCompletionClient:
    """Build a single :class:`OpenAIChatCompletionClient` configured for Gemini.

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
    return OpenAIChatCompletionClient[OpenAIChatCompletionOptions[None]](
        model=model,
        api_key=api_key,
        base_url=GEMINI_OPENAI_BASE_URL,
    )

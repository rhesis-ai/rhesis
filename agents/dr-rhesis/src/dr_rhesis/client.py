"""Gemini ChatGenerator factory for Dr-Rhesis.

All LLM calls in the agent share a single generator built here. Individual
components must not construct their own generators.
"""

from __future__ import annotations

import os
from typing import Final

from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator

DEFAULT_MODEL: Final[str] = "gemini-3.1-flash-lite"


def build_chat_generator() -> GoogleGenAIChatGenerator:
    """Build a :class:`GoogleGenAIChatGenerator` for Gemini.

    Reads ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) from the environment and
    optionally ``DR_RHESIS_MODEL`` to override the default model id.

    Raises:
        RuntimeError: if no Gemini API key is set.
    """
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is required to run Dr-Rhesis. "
            "Set one in your environment or .env file."
        )
    model = os.environ.get("DR_RHESIS_MODEL", DEFAULT_MODEL)
    return GoogleGenAIChatGenerator(model=model)


__all__ = ["DEFAULT_MODEL", "build_chat_generator"]

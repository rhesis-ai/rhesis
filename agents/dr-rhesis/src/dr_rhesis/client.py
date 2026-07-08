"""Gemini ChatGenerator factory for Dr-Rhesis.

All LLM calls in the agent share a single generator built here. Individual
components must not construct their own generators.
"""

from __future__ import annotations

import os
from typing import Final

from haystack.utils import Secret
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator

DEFAULT_MODEL: Final[str] = "gemini-3.1-flash-lite"

API_KEY_ENV_VARS: Final[tuple[str, str]] = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def build_chat_generator() -> GoogleGenAIChatGenerator:
    """Build a :class:`GoogleGenAIChatGenerator` for Gemini.

    Reads ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) from the environment and
    optionally ``DR_RHESIS_MODEL`` to override the default model id.

    Raises:
        RuntimeError: if no Gemini API key is set.
    """
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is required to run Dr-Rhesis. "
            "Set one in your environment or .env file."
        )
    model = os.environ.get("DR_RHESIS_MODEL", DEFAULT_MODEL)
    # Pass the key source explicitly rather than relying on the component's
    # default env lookup, so the resolved credential is unambiguous.
    return GoogleGenAIChatGenerator(
        api_key=Secret.from_env_var(list(API_KEY_ENV_VARS), strict=False),
        model=model,
    )


__all__ = ["API_KEY_ENV_VARS", "DEFAULT_MODEL", "build_chat_generator"]

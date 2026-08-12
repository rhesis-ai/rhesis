"""Gemini model factory for Reg-Advisor.

All LLM calls in the agent share a single model built here. The coordinator and its
specialists must not construct their own.
"""

from __future__ import annotations

import os
from typing import Final

from google.adk.models import BaseLlm, Gemini

DEFAULT_MODEL: Final[str] = "gemini-3.1-flash-lite"
MODEL_ENV_VAR: Final[str] = "REG_ADVISOR_MODEL"
API_KEY_ENV_VARS: Final[tuple[str, str]] = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
VERTEX_ENV_VAR: Final[str] = "GOOGLE_GENAI_USE_VERTEXAI"

MISSING_KEY_MESSAGE: Final[str] = (
    "No Gemini API key found. Set GOOGLE_API_KEY (or GEMINI_API_KEY) in your environment or "
    "in .env, or set GOOGLE_GENAI_USE_VERTEXAI=1 with GOOGLE_CLOUD_PROJECT and "
    "GOOGLE_CLOUD_LOCATION to use Vertex AI instead."
)


def _using_vertex() -> bool:
    return os.getenv(VERTEX_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


def build_model() -> BaseLlm:
    """Build the shared Gemini model.

    Raises ``RuntimeError`` with a readable message when no credential is configured. The app
    and the CLIs both special-case that message, so a missing key surfaces as a 503 with the
    real explanation rather than a generic 500.
    """
    if not _using_vertex() and not any(os.getenv(name) for name in API_KEY_ENV_VARS):
        raise RuntimeError(MISSING_KEY_MESSAGE)
    return Gemini(model=os.getenv(MODEL_ENV_VAR) or DEFAULT_MODEL)


__all__ = [
    "API_KEY_ENV_VARS",
    "DEFAULT_MODEL",
    "MISSING_KEY_MESSAGE",
    "MODEL_ENV_VAR",
    "VERTEX_ENV_VAR",
    "build_model",
]

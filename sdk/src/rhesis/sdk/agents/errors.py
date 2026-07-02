"""User-facing error messages for agent failures."""

from __future__ import annotations

import re
from typing import Union

_DEFAULT_MESSAGE = (
    "Something went wrong while processing your message. "
    "Please try again. If the problem persists, check your generation "
    "model settings in workspace settings."
)

_MODEL_SETTINGS_HINT = "Check your generation model settings in workspace settings and try again."

# litellm and provider exceptions often stringify with a full traceback.
_TRACEBACK_SPLIT = re.compile(r"\n\s*Traceback \(most recent call last\):", re.IGNORECASE)


def _strip_traceback(text: str) -> str:
    """Return only the message portion before any embedded traceback."""
    parts = _TRACEBACK_SPLIT.split(text, maxsplit=1)
    return parts[0].strip()


def _normalize(text: str) -> str:
    """Collapse noisy provider prefixes like ``litellm.APIConnectionError:``."""
    cleaned = _strip_traceback(text)
    if not cleaned:
        return ""

    # Drop ``module.ExceptionName:`` prefix when present.
    if ":" in cleaned:
        head, _, tail = cleaned.partition(":")
        if "." in head and tail.strip():
            return tail.strip()
    return cleaned


def format_user_facing_error(error: Union[BaseException, str, None]) -> str:
    """Convert an internal agent/LLM failure into a safe user message.

    Strips tracebacks and maps common provider/transport failures to
    actionable guidance. Full details should be logged server-side.
    """
    if error is None:
        return _DEFAULT_MESSAGE

    raw = str(error).strip()
    if not raw:
        return _DEFAULT_MESSAGE

    text = _normalize(raw).lower()

    if "event loop" in text or "different event loop" in text:
        return "The Architect hit a temporary processing issue. Please send your message again."

    if "rate limit" in text or "ratelimit" in text or "429" in text:
        return "The AI provider rate limit was reached. Please wait a moment and try again."

    if "timeout" in text or "timed out" in text:
        return "The request timed out. Please try again."

    if any(
        token in text
        for token in (
            "authentication",
            "unauthorized",
            "invalid api key",
            "api key",
            "permission denied",
            "401",
            "403",
        )
    ):
        return f"Could not connect to the configured AI provider. {_MODEL_SETTINGS_HINT}"

    if any(
        token in text
        for token in (
            "apiconnectionerror",
            "connection error",
            "connection refused",
            "failed to connect",
            "service unavailable",
            "503",
            "502",
            "bad gateway",
        )
    ):
        return "The AI service is temporarily unavailable. Please try again in a moment."

    if "not capable" in text or "structured-output" in text:
        return raw if "generation model" in raw.lower() else _normalize(raw)

    # Already user-facing (e.g. validation messages from the WS handler).
    if "traceback" not in raw.lower() and len(_normalize(raw)) <= 300:
        normalized = _normalize(raw)
        if normalized and not normalized.startswith("/"):
            return normalized

    return _DEFAULT_MESSAGE

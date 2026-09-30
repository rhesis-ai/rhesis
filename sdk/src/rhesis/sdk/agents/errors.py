"""User-facing error messages for agent failures."""

from __future__ import annotations

import re
from typing import Optional, Union

_DEFAULT_MESSAGE = (
    "Something went wrong while processing your message. "
    "Please try again. If the problem persists, check your generation "
    "model settings in workspace settings."
)

_MODEL_SETTINGS_HINT = "Check your generation model settings in workspace settings and try again."

#: Stable code for "no usable model is set up". Matches the backend's
#: ``rhesis.backend.app.utils.model_errors.MODEL_NOT_CONFIGURED``.
MODEL_NOT_CONFIGURED = "model_not_configured"

_MODEL_NOT_CONFIGURED_MESSAGE = (
    "No usable AI model is set up. Open the Models page to enter a Rhesis platform "
    "API key, or add a model from your own provider."
)

# Fallback for errors that carry no ``error_code``: the native provider's missing key.
_NOT_CONFIGURED_MARKERS = ("rhesis_api_key is not set",)

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


def model_error_code(error: Union[BaseException, str, None]) -> Optional[str]:
    """Return ``MODEL_NOT_CONFIGURED`` when *error* means no usable model is set up."""
    if error is None:
        return None
    code = getattr(error, "error_code", None)
    if code:
        return code
    text = _normalize(str(error)).lower()
    if any(marker in text for marker in _NOT_CONFIGURED_MARKERS):
        return MODEL_NOT_CONFIGURED
    return None


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

    if model_error_code(error) == MODEL_NOT_CONFIGURED:
        # A coded error is already worded for the user; a bare missing key is not.
        if getattr(error, "error_code", None) and len(raw) <= 300:
            return raw
        return _MODEL_NOT_CONFIGURED_MESSAGE

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

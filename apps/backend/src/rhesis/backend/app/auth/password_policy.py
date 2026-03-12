"""
NIST SP 800-63B-4 aligned configurable password policy.

Environment variables:
    PASSWORD_MIN_LENGTH: Minimum password length (default: 12)
    PASSWORD_MAX_LENGTH: Maximum password length (default: 128)
    PASSWORD_CHECK_BREACHED: Check against HaveIBeenPwned (default: true)
    PASSWORD_MIN_STRENGTH_SCORE: Minimum zxcvbn score 0-4 (default: 2)
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx
from fastapi import HTTPException, status
from zxcvbn import zxcvbn

logger = logging.getLogger(__name__)

_HIBP_API_URL = "https://api.pwnedpasswords.com/range"

_policy_cache: "PasswordPolicyConfig | None" = None

_CONTEXT_BLOCKED_WORDS = frozenset({"rhesis"})

_MIN_CONTEXT_WORD_LENGTH = 4


@dataclass
class PasswordPolicyConfig:
    """Password policy configuration (NIST SP 800-63B-4 aligned)."""

    min_length: int
    max_length: int
    check_breached: bool
    min_strength_score: int
    context_blocked_words: frozenset[str] = field(
        default_factory=lambda: _CONTEXT_BLOCKED_WORDS,
    )


def get_password_policy() -> PasswordPolicyConfig:
    """Get the password policy config (cached, env var overrides)."""
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache

    min_length = 12
    max_length = 128
    check_breached = True
    min_strength_score = 2

    if v := os.getenv("PASSWORD_MIN_LENGTH"):
        try:
            min_length = int(v)
            if min_length < 1:
                min_length = 12
        except ValueError:
            pass

    if v := os.getenv("PASSWORD_MAX_LENGTH"):
        try:
            max_length = int(v)
            if max_length < min_length:
                max_length = min_length
        except ValueError:
            pass

    check_breached = os.getenv("PASSWORD_CHECK_BREACHED", "true").lower() in ("true", "1", "yes")

    if v := os.getenv("PASSWORD_MIN_STRENGTH_SCORE"):
        try:
            score = int(v)
            if 0 <= score <= 4:
                min_strength_score = score
        except ValueError:
            pass

    _policy_cache = PasswordPolicyConfig(
        min_length=min_length,
        max_length=max_length,
        check_breached=check_breached,
        min_strength_score=min_strength_score,
    )
    return _policy_cache


def _build_user_inputs(
    context: Optional[dict[str, str]],
) -> list[str]:
    """Derive zxcvbn user_inputs and context words from caller-supplied context."""
    inputs: list[str] = list(_CONTEXT_BLOCKED_WORDS)
    if not context:
        return inputs

    if email := context.get("email"):
        local_part = email.split("@")[0] if "@" in email else email
        if local_part:
            inputs.append(local_part)

    if name := context.get("name"):
        for token in name.split():
            stripped = token.strip()
            if stripped:
                inputs.append(stripped)

    return inputs


def _check_context_words(
    password: str,
    context: Optional[dict[str, str]],
) -> Optional[str]:
    """
    Return the matched word if the password contains a context-specific word,
    else None. Only words >= _MIN_CONTEXT_WORD_LENGTH chars are checked.
    """
    pw_lower = password.casefold()
    words = _build_user_inputs(context)
    for word in words:
        w = word.casefold()
        if len(w) >= _MIN_CONTEXT_WORD_LENGTH and w in pw_lower:
            return word
    return None


def _check_strength_score(
    password: str,
    context: Optional[dict[str, str]],
) -> tuple[int, str | None]:
    """
    Evaluate password strength with zxcvbn.
    Returns (score, feedback_warning). score is 0-4.
    zxcvbn's built-in dictionaries cover ~30k common passwords,
    names, and keyboard patterns.
    """
    user_inputs = _build_user_inputs(context)
    result = zxcvbn(password, user_inputs=user_inputs)
    score: int = result["score"]
    warning: str | None = None
    feedback = result.get("feedback", {})
    if feedback.get("warning"):
        warning = feedback["warning"]
    elif feedback.get("suggestions"):
        warning = feedback["suggestions"][0]
    return score, warning


def validate_password(
    password: str,
    context: Optional[dict[str, str]] = None,
) -> None:
    """
    Validate password against NIST-aligned policy.
    Raises HTTPException(400) on failure.

    ``context`` is an optional dict with ``email`` and/or ``name`` keys
    used for context-specific word blocking and zxcvbn user_inputs.
    """
    if not isinstance(password, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be a string",
        )

    if not password.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must not be entirely whitespace",
        )

    policy = get_password_policy()

    if len(password) < policy.min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Password must be at least {policy.min_length} characters"),
        )

    if len(password) > policy.max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Password must be at most {policy.max_length} characters"),
        )

    matched_word = _check_context_words(password, context)
    if matched_word:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Password must not contain your name, email, or the service name."),
        )

    if policy.min_strength_score > 0:
        score, warning = _check_strength_score(password, context)
        if score < policy.min_strength_score:
            detail = "Password is too weak. Please choose a stronger password."
            if warning:
                detail = f"{detail} Hint: {warning}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

    if policy.check_breached and _check_breached_sync(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("This password has been found in a data breach. Please choose another."),
        )


async def check_breached_password(password: str) -> bool:
    """
    Check if password appears in HaveIBeenPwned breach database.

    Uses k-Anonymity: only the first 5 chars of the SHA-1 hash
    are sent; full password never leaves the client.
    """
    return _check_breached_sync(password)


def _check_breached_sync(password: str) -> bool:
    """
    Synchronous breached password check via HaveIBeenPwned k-Anonymity API.
    Returns True if the password has been breached.
    """
    digest = hashlib.sha1(password.encode("utf-8", errors="replace")).hexdigest()
    prefix = digest[:5].upper()
    suffix = digest[5:].upper()

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{_HIBP_API_URL}/{prefix}")
            response.raise_for_status()
            body = response.text
    except httpx.HTTPError as e:
        logger.warning("HaveIBeenPwned API request failed: %s", e)
        return False

    for line in body.splitlines():
        parts = line.strip().split(":")
        if len(parts) == 2 and parts[0] == suffix:
            count = int(parts[1], 10)
            return count > 0

    return False


def reset_policy_cache() -> None:
    """Reset the cached policy config. Useful for testing."""
    global _policy_cache
    _policy_cache = None

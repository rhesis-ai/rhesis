"""
NIST-aligned configurable password policy.

Environment variables:
    PASSWORD_MIN_LENGTH: Minimum password length (default: 8)
    PASSWORD_MAX_LENGTH: Maximum password length (default: 128)
    PASSWORD_CHECK_BREACHED: Set to 'true' to check against HaveIBeenPwned (default: false)
"""

import hashlib
import os
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from rhesis.backend.logging import logger

# HaveIBeenPwned k-Anonymity API
_HIBP_API_URL = "https://api.pwnedpasswords.com/range"

# Module-level cache for policy config
_policy_cache: "PasswordPolicyConfig | None" = None


@dataclass
class PasswordPolicyConfig:
    """Password policy configuration (NIST-aligned)."""

    min_length: int
    max_length: int
    check_breached: bool


def get_password_policy() -> PasswordPolicyConfig:
    """Get the password policy config (cached, env var overrides)."""
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache

    min_length = 8
    max_length = 128
    check_breached = False

    if v := os.getenv("PASSWORD_MIN_LENGTH"):
        try:
            min_length = int(v)
            if min_length < 1:
                min_length = 8
        except ValueError:
            pass

    if v := os.getenv("PASSWORD_MAX_LENGTH"):
        try:
            max_length = int(v)
            if max_length < min_length:
                max_length = min_length
        except ValueError:
            pass

    check_breached = os.getenv("PASSWORD_CHECK_BREACHED", "false").lower() in ("true", "1", "yes")

    _policy_cache = PasswordPolicyConfig(
        min_length=min_length,
        max_length=max_length,
        check_breached=check_breached,
    )
    return _policy_cache


def validate_password(password: str) -> None:
    """
    Validate password against policy. Raises HTTPException on failure.

    Checks min/max length. If PASSWORD_CHECK_BREACHED is enabled,
    synchronously checks against HaveIBeenPwned (blocks briefly).
    """
    if not isinstance(password, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be a string",
        )

    policy = get_password_policy()

    if len(password) < policy.min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {policy.min_length} characters",
        )

    if len(password) > policy.max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {policy.max_length} characters",
        )

    if policy.check_breached and _check_breached_sync(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has been found in a data breach. Please choose another.",
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
        # On API failure, allow the password (fail open for availability)
        return False

    for line in body.splitlines():
        parts = line.strip().split(":")
        if len(parts) == 2 and parts[0] == suffix:
            count = int(parts[1], 10)
            return count > 0

    return False

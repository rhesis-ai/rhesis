"""Redaction helpers for logs and recorded requests."""

from typing import Any, Optional


def redact_email(email: str) -> str:
    """
    Redact email for logging: show first two chars and domain.

    Example: "alice@example.com" -> "al***@example.com"
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        return f"{local}***@{domain}"
    return f"{local[:2]}***@{domain}"


# Same placeholder header redaction uses (services/invokers/common/headers.py).
SECRET_PLACEHOLDER = "***REDACTED***"


def mask_secret(value: Any, secret: Optional[str]) -> Any:
    """A copy of *value* with every occurrence of *secret* in its strings replaced."""
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, SECRET_PLACEHOLDER)
    if isinstance(value, dict):
        return {key: mask_secret(item, secret) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(mask_secret(item, secret) for item in value)
    return value

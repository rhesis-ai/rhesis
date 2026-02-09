"""Redaction helpers for logging PII."""


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

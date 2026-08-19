"""Key-name based redaction, shared by telemetry and the events layer.

Moved from ``telemetry/instrumentation.py`` so both use one list instead of
two that can drift apart. Applied once, in the events dispatcher, before any
sink sees an event -- per-sink redaction fails open the moment someone adds a
sink and forgets.

This inspects key names, never values: a field named ``prompt``, ``content``,
``body``, ``response`` or ``message`` passes cleanly while carrying arbitrary
customer data. That is why ``PlatformEvent`` subclasses declare narrow typed
fields for identifiers and counts rather than a free-form payload -- this
filter is a backstop, not the primary control.
"""

# Exact-match keys this list's substring rule does not already cover.
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "session_token",
    "access_token",
    "refresh_token",
    "bearer",
    "email",
    "ssn",
    "credit_card",
}

# Substring rule: catches variations the exact-match set misses, e.g.
# "user_email" (not caught by the "email" exact match above) or "api_secret".
SENSITIVE_SUBSTRINGS = ("password", "token", "key", "secret", "email")


def redact_metadata(metadata: dict) -> dict:
    """Drop keys that look sensitive by name. Case insensitive.

    >>> redact_metadata({"username": "john", "password": "secret"})
    {'username': 'john'}
    >>> redact_metadata({"user_email": "a@b.com", "user_agent": "Mozilla"})
    {'user_agent': 'Mozilla'}
    """
    return {
        k: v
        for k, v in metadata.items()
        if k.lower() not in SENSITIVE_KEYS and not any(s in k.lower() for s in SENSITIVE_SUBSTRINGS)
    }

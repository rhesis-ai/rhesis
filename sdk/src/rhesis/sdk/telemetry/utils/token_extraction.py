"""
Backwards-compatible re-export of the token-usage extraction helpers.

These moved to ``rhesis.telemetry.token_extraction`` so that framework integrations can depend on
the lightweight ``rhesis[telemetry]`` package instead of the full SDK. The module is pure stdlib.

New code should import from ``rhesis.telemetry.token_extraction``.
"""

from rhesis.telemetry.token_extraction import extract_token_usage, get_first_value

__all__ = ["extract_token_usage", "get_first_value"]

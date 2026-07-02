"""Tests for user-facing agent error formatting."""

from rhesis.sdk.agents.errors import format_user_facing_error


class TestFormatUserFacingError:
    def test_strips_embedded_traceback(self):
        raw = (
            "litellm.APIConnectionError: connection failed\n"
            "Traceback (most recent call last):\n"
            '  File "/app/litellm/main.py", line 639, in acompletion\n'
            "    response = await init_response\n"
            "RuntimeError: boom"
        )
        message = format_user_facing_error(raw)
        assert "Traceback" not in message
        assert "litellm" not in message
        assert "main.py" not in message

    def test_event_loop_error_is_friendly(self):
        raw = (
            "litellm.APIConnectionError: <asyncio.locks.Lock object "
            "at 0x7c1450015150 [unlocked, waiters:2]> is bound to a "
            "different event loop"
        )
        message = format_user_facing_error(raw)
        assert "asyncio" not in message
        assert "event loop" not in message.lower()
        assert "try again" in message.lower() or "again" in message.lower()

    def test_rate_limit_message(self):
        message = format_user_facing_error("RateLimitError: 429 Too Many Requests")
        assert "rate limit" in message.lower()

    def test_timeout_message(self):
        message = format_user_facing_error("Request timed out after 60s")
        assert "timed out" in message.lower()

    def test_auth_message(self):
        message = format_user_facing_error("AuthenticationError: invalid api key")
        assert "generation model settings" in message.lower()

    def test_preserves_short_user_messages(self):
        message = format_user_facing_error("Session not found or access denied")
        assert message == "Session not found or access denied"

    def test_none_returns_default(self):
        message = format_user_facing_error(None)
        assert "something went wrong" in message.lower()

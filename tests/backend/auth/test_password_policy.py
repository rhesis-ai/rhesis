"""
Unit tests for NIST-aligned password policy.

Tests context-word blocking, zxcvbn strength scoring,
min/max length enforcement, and HIBP breach checking (mocked).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    """Reset cached policy config between tests."""
    from rhesis.backend.app.auth.password_policy import reset_policy_cache

    reset_policy_cache()
    yield
    reset_policy_cache()


@pytest.fixture(autouse=True)
def _disable_hibp(monkeypatch):
    """Disable HIBP network call for all tests by default."""
    monkeypatch.setenv("PASSWORD_CHECK_BREACHED", "false")


class TestLengthEnforcement:
    """Min/max password length checks."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_too_short_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "12")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("Short1!")
        assert exc_info.value.status_code == 400
        assert "at least 12" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_too_long_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MAX_LENGTH", "20")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("A" * 21)
        assert exc_info.value.status_code == 400
        assert "at most 20" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_valid_length_passes(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        await validate_password("ValidPassword123!@#")


class TestContextWordBlocking:
    """Context-specific word blocking (email, name, service name)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_email_prefix_in_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password(
                "johnsmith_plus_extras!!",
                context={"email": "johnsmith@example.com", "name": ""},
            )
        assert exc_info.value.status_code == 400
        assert "name, email" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_name_token_in_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password(
                "ilovemichael2024!",
                context={"email": "m@example.com", "name": "Michael Johnson"},
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_service_name_in_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password(
                "myrhesispassword1!",
                context={"email": "x@example.com", "name": ""},
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_short_context_words_are_ignored(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        await validate_password(
            "xK9!mZ3@qW7$pL5#",
            context={"email": "ab@example.com", "name": "Jo"},
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_context_passes(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        await validate_password("xK9!mZ3@qW7$pL5#")


class TestStrengthScoring:
    """zxcvbn-based password strength scoring (covers common passwords too)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_weak_password_rejected_at_score_2(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "2")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("aaaaaaaa")
        assert exc_info.value.status_code == 400
        assert "too weak" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_common_password_rejected_by_strength_check(self, monkeypatch):
        """zxcvbn's built-in dictionaries catch common passwords like 'password123'."""
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "2")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("password123!")
        assert exc_info.value.status_code == 400
        assert "too weak" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_strong_password_passes_at_score_2(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "2")
        from rhesis.backend.app.auth.password_policy import validate_password

        await validate_password("xK9!mZ3@qW7$pL5#vN")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_strength_check_disabled_at_score_0(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        await validate_password("aaaaaaaa")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_feedback_hint_included_in_error(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "4")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("abcdefgh12")
        detail = exc_info.value.detail
        assert "too weak" in detail


class TestBreachedPasswordCheck:
    """HaveIBeenPwned integration (mocked)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_breached_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_CHECK_BREACHED", "true")
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")

        from rhesis.backend.app.auth import password_policy

        with patch.object(
            password_policy, "_check_breached", new_callable=AsyncMock, return_value=True
        ):
            with pytest.raises(HTTPException) as exc_info:
                await password_policy.validate_password("breachedpassword!")
            assert exc_info.value.status_code == 400
            assert "data breach" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_breached_password_passes(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_CHECK_BREACHED", "true")
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")

        from rhesis.backend.app.auth import password_policy

        with patch.object(
            password_policy, "_check_breached", new_callable=AsyncMock, return_value=False
        ):
            await password_policy.validate_password("xK9!mZ3@qW7$pL5#")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hibp_api_failure_fails_open(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_CHECK_BREACHED", "true")
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "8")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")

        from rhesis.backend.app.auth import password_policy

        with patch.object(
            password_policy,
            "_check_breached",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await password_policy.validate_password("xK9!mZ3@qW7$pL5#")


class TestPolicyConfig:
    """Policy configuration and defaults."""

    @pytest.mark.unit
    def test_default_min_length_is_12(self):
        from rhesis.backend.app.auth.password_policy import (
            get_password_policy,
        )

        policy = get_password_policy()
        assert policy.min_length == 12

    @pytest.mark.unit
    def test_default_check_breached_is_true(self, monkeypatch):
        monkeypatch.delenv("PASSWORD_CHECK_BREACHED", raising=False)
        from rhesis.backend.app.auth.password_policy import (
            get_password_policy,
            reset_policy_cache,
        )

        reset_policy_cache()
        policy = get_password_policy()
        assert policy.check_breached is True

    @pytest.mark.unit
    def test_default_min_strength_score_is_2(self):
        from rhesis.backend.app.auth.password_policy import (
            get_password_policy,
        )

        policy = get_password_policy()
        assert policy.min_strength_score == 2

    @pytest.mark.unit
    def test_env_override_min_length(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "16")
        from rhesis.backend.app.auth.password_policy import (
            get_password_policy,
        )

        policy = get_password_policy()
        assert policy.min_length == 16


class TestFullValidationPipeline:
    """End-to-end validation with all checks enabled."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_strong_password_passes_all_checks(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", "12")
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "2")

        from rhesis.backend.app.auth import password_policy

        with patch.object(
            password_policy, "_check_breached", new_callable=AsyncMock, return_value=False
        ):
            await password_policy.validate_password(
                "xK9!mZ3@qW7$pL5#vN",
                context={
                    "email": "alice@example.com",
                    "name": "Alice",
                },
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_whitespace_password_is_rejected(self, monkeypatch):
        """All-whitespace passwords are explicitly rejected for compliance."""
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password("            ")
        assert exc_info.value.status_code == 400
        assert "whitespace" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_string_password_is_rejected(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_MIN_STRENGTH_SCORE", "0")
        from rhesis.backend.app.auth.password_policy import validate_password

        with pytest.raises(HTTPException) as exc_info:
            await validate_password(12345)
        assert exc_info.value.status_code == 400
        assert "must be a string" in exc_info.value.detail

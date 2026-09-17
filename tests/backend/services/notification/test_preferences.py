"""Tests for services.notification.preferences.email_enabled().

The flags are unset for every user who predates the setting, so the default
("send it") is the behaviour that matters most here.
"""

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.services.notification import EmailNotificationKind, email_enabled

ALL_KINDS = list(EmailNotificationKind)


def _user(settings: dict | None) -> models.User:
    """A detached User carrying only the settings blob under test."""
    return models.User(email="someone@rhesis-test.com", user_settings=settings)


@pytest.mark.unit
class TestEmailEnabled:
    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_defaults_to_enabled_when_never_set(self, kind):
        assert email_enabled(_user({"version": 1}), kind) is True

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_defaults_to_enabled_when_settings_empty(self, kind):
        assert email_enabled(_user(None), kind) is True

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_disabled_when_switched_off(self, kind):
        user = _user({"notifications": {"email": {kind.value: False}}})

        assert email_enabled(user, kind) is False

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_enabled_when_switched_back_on(self, kind):
        user = _user({"notifications": {"email": {kind.value: True}}})

        assert email_enabled(user, kind) is True

    def test_kinds_are_independent(self):
        user = _user({"notifications": {"email": {"job_completion": False}}})

        assert email_enabled(user, EmailNotificationKind.JOB_COMPLETION) is False
        assert email_enabled(user, EmailNotificationKind.TASK_ASSIGNMENT) is True

    def test_unreadable_settings_still_send(self):
        """A blob we can't read a preference off must not silently swallow the email."""
        user = _user({"notifications": {"email": "not-a-dict"}})

        assert email_enabled(user, EmailNotificationKind.JOB_COMPLETION) is True

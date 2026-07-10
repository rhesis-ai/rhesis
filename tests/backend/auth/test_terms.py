"""Tests for terms acceptance helpers."""

from datetime import datetime, timezone

from rhesis.backend.app.auth.terms import (
    CURRENT_TERMS_VERSION,
    record_terms_acceptance,
    user_has_accepted_current_terms,
)
from rhesis.backend.app.models.user import User


def test_user_has_accepted_current_terms_false_when_unset():
    user = User(email="a@example.com")
    assert user_has_accepted_current_terms(user) is False


def test_user_has_accepted_current_terms_false_for_outdated_version():
    user = User(
        email="a@example.com",
        terms_accepted_at=datetime.now(timezone.utc),
        terms_accepted_version="0.9",
    )
    assert user_has_accepted_current_terms(user) is False


def test_record_terms_acceptance_sets_current_version():
    user = User(email="a@example.com")
    record_terms_acceptance(user)
    assert user.terms_accepted_at is not None
    assert user.terms_accepted_version == CURRENT_TERMS_VERSION
    assert user_has_accepted_current_terms(user) is True

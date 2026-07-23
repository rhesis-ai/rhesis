"""Tests for terms acceptance helpers."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from rhesis.backend.app.auth.terms import (
    CURRENT_TERMS_VERSION,
    TERMS_TRACKING_STARTED_AT,
    record_terms_acceptance,
    user_has_accepted_current_terms,
    user_has_prior_terms_acceptance,
)
from rhesis.backend.app.models.user import User

_PRE_TRACKING = TERMS_TRACKING_STARTED_AT - timedelta(days=1)
_POST_TRACKING = TERMS_TRACKING_STARTED_AT + timedelta(days=1)


def test_user_has_accepted_current_terms_false_when_unset():
    user = User(email="a@example.com")
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is False


def test_pre_tracking_onboarded_user_without_terms_is_grandfathered():
    """Pre-tracking accounts accepted T&Cs at signup; do not re-prompt for 1.0."""
    user = User(
        email="a@example.com",
        organization_id=uuid4(),
        created_at=_PRE_TRACKING,
    )
    assert user_has_accepted_current_terms(user) is True
    assert user_has_prior_terms_acceptance(user) is True


def test_post_tracking_onboarded_user_without_terms_is_not_grandfathered():
    """Org membership after tracking shipped is not enough without a terms record."""
    user = User(
        email="a@example.com",
        organization_id=uuid4(),
        created_at=_POST_TRACKING,
    )
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is False


def test_grandfathering_does_not_apply_after_version_bump(monkeypatch):
    """Once CURRENT_TERMS_VERSION moves past baseline, pre-tracking users must re-accept."""
    import rhesis.backend.app.auth.terms as terms_mod

    monkeypatch.setattr(terms_mod, "CURRENT_TERMS_VERSION", "2.0")
    user = User(
        email="a@example.com",
        organization_id=uuid4(),
        created_at=_PRE_TRACKING,
    )
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is True


def test_user_has_accepted_current_terms_false_for_outdated_version():
    user = User(
        email="a@example.com",
        user_settings={
            "terms": {"accepted_at": datetime.now(timezone.utc).isoformat(), "version": "0.9"}
        },
    )
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is True


def test_record_terms_acceptance_sets_current_version():
    user = User(email="a@example.com")
    record_terms_acceptance(user)
    terms = (user.user_settings or {}).get("terms") or {}
    assert terms.get("accepted_at")
    assert terms.get("version") == CURRENT_TERMS_VERSION
    assert user_has_accepted_current_terms(user) is True


def test_record_terms_acceptance_persists_for_grandfathered_user():
    """Explicit accept should write a record even when grandfathering already applies."""
    user = User(
        email="a@example.com",
        organization_id=uuid4(),
        created_at=_PRE_TRACKING,
    )
    assert user_has_accepted_current_terms(user) is True
    record_terms_acceptance(user)
    terms = (user.user_settings or {}).get("terms") or {}
    assert terms.get("accepted_at")
    assert terms.get("version") == CURRENT_TERMS_VERSION


def test_record_terms_acceptance_is_idempotent():
    user = User(email="a@example.com")
    record_terms_acceptance(user)
    first_timestamp = ((user.user_settings or {}).get("terms") or {}).get("accepted_at")
    record_terms_acceptance(user)
    assert ((user.user_settings or {}).get("terms") or {}).get("accepted_at") == first_timestamp

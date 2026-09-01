"""Tests for terms acceptance helpers."""

from datetime import datetime, timezone

from rhesis.backend.app.auth.terms import (
    CURRENT_TERMS_VERSION,
    record_terms_acceptance,
    user_has_accepted_current_terms,
    user_has_prior_terms_acceptance,
)
from rhesis.backend.app.models.user import User


def test_user_has_accepted_current_terms_false_when_unset():
    user = User(email="a@example.com")
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is False


def test_user_has_accepted_current_terms_false_for_outdated_version():
    user = User(
        email="a@example.com",
        user_settings={
            "terms": {"accepted_at": datetime.now(timezone.utc).isoformat(), "version": "0.9"}
        },
    )
    assert user_has_accepted_current_terms(user) is False
    assert user_has_prior_terms_acceptance(user) is True


def test_backfilled_baseline_users_must_re_accept():
    """The population this bump exists for.

    Every user onboarded before terms tracking carries ``"1.0"``, written once
    by the ``b5c6d7e8f9a0`` backfill. Version 2.0 replaces the public preview
    terms with the commercial SaaS terms -- a different document, not an
    amendment -- so that whole population has to be prompted again. A bump that
    left them reading as current would silently hold them to terms they never
    saw.

    ``user_has_prior_terms_acceptance`` staying true is what makes the frontend
    gate say "Updated Terms" rather than showing them first-run copy.
    """
    backfill_baseline = "1.0"
    assert CURRENT_TERMS_VERSION != backfill_baseline, (
        "CURRENT_TERMS_VERSION is back at the backfill baseline, so no "
        "pre-existing user would be asked to re-accept."
    )

    user = User(
        email="a@example.com",
        user_settings={
            "terms": {
                "accepted_at": datetime.now(timezone.utc).isoformat(),
                "version": backfill_baseline,
            }
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


def test_record_terms_acceptance_is_idempotent():
    user = User(email="a@example.com")
    record_terms_acceptance(user)
    first_timestamp = ((user.user_settings or {}).get("terms") or {}).get("accepted_at")
    record_terms_acceptance(user)
    assert ((user.user_settings or {}).get("terms") or {}).get("accepted_at") == first_timestamp

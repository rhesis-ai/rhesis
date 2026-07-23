"""Terms and Conditions acceptance tracking.

New users accept the active T&C version during onboarding (step 0). Acceptance
is stored in ``user_settings.terms`` (``version`` + ``accepted_at``) so they
are not prompted again until the version changes.

Users who completed onboarding before server-side tracking existed (acceptance
was localStorage-only) have no ``user_settings.terms`` record. They are
grandfathered as having accepted ``BASELINE_TERMS_VERSION`` at signup — the
post-login gate must not re-prompt them until ``CURRENT_TERMS_VERSION`` is
bumped past that baseline.

Bump ``CURRENT_TERMS_VERSION`` (and ``CURRENT_TERMS_EFFECTIVE_DATE``) when
publishing new terms; users with an older accepted version must
re-accept before continuing.
"""

from datetime import date, datetime, timezone

from rhesis.backend.app.models.user import User

# Active T&C version (effective 2025-09-01).
CURRENT_TERMS_VERSION = "1.0"
CURRENT_TERMS_EFFECTIVE_DATE = date(2025, 9, 1)

# Version that shipped with server-side tracking. Pre-tracking onboarded users
# without a persisted record are treated as having accepted this version.
BASELINE_TERMS_VERSION = "1.0"

# Server-side terms tracking shipped in #2144 (merged 2026-07-14). Accounts
# created before this instant may lack ``user_settings.terms`` even though they
# accepted at signup. Accounts created on/after this instant must have an
# explicit record — organization membership alone is not enough (admin-created
# / imported users, invitees, etc.).
TERMS_TRACKING_STARTED_AT = datetime(2026, 7, 14, tzinfo=timezone.utc)


def _user_terms(user: User) -> dict:
    return (user.user_settings or {}).get("terms") or {}


def _created_at_utc(user: User) -> datetime | None:
    created_at = user.created_at
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(timezone.utc)


def _is_pre_tracking_onboarded_user(user: User) -> bool:
    """True for org members created before server-side terms tracking."""
    if not user.organization_id:
        return False
    created_at = _created_at_utc(user)
    if created_at is None:
        return False
    return created_at < TERMS_TRACKING_STARTED_AT


def _is_grandfathered_baseline_acceptance(user: User) -> bool:
    """Pre-tracking onboarded users with no terms row accepted baseline at signup."""
    if CURRENT_TERMS_VERSION != BASELINE_TERMS_VERSION:
        return False
    if _user_terms(user).get("accepted_at"):
        return False
    return _is_pre_tracking_onboarded_user(user)


def user_has_accepted_current_terms(user: User) -> bool:
    """Return whether the user accepted the currently active T&C version."""
    terms = _user_terms(user)
    if bool(terms.get("accepted_at")) and terms.get("version") == CURRENT_TERMS_VERSION:
        return True
    return _is_grandfathered_baseline_acceptance(user)


def user_has_prior_terms_acceptance(user: User) -> bool:
    """Return whether the user accepted any T&C version (possibly outdated).

    Pre-tracking onboarded accounts imply signup-time acceptance even when the
    record was never persisted.
    """
    if bool(_user_terms(user).get("accepted_at")):
        return True
    return _is_pre_tracking_onboarded_user(user)


def record_terms_acceptance(user: User) -> None:
    """Persist acceptance of the current T&C version (no-op if already current)."""
    terms = _user_terms(user)
    if bool(terms.get("accepted_at")) and terms.get("version") == CURRENT_TERMS_VERSION:
        return
    settings = dict(user.user_settings or {})
    settings["terms"] = {
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "version": CURRENT_TERMS_VERSION,
    }
    user.user_settings = settings

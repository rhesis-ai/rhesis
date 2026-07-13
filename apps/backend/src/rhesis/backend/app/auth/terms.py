"""Terms and Conditions acceptance tracking.

New users accept the active T&C version during onboarding (step 0). Acceptance
is stored on the user record so they are not prompted again until the version
changes.

Bump ``CURRENT_TERMS_VERSION`` (and ``CURRENT_TERMS_EFFECTIVE_DATE``) when
publishing new terms; users with an older accepted version must
re-accept before continuing.
"""

from datetime import date, datetime, timezone

from rhesis.backend.app.models.user import User

# Active T&C version (effective 2025-09-01).
CURRENT_TERMS_VERSION = "1.0"
CURRENT_TERMS_EFFECTIVE_DATE = date(2025, 9, 1)


def user_has_accepted_current_terms(user: User) -> bool:
    """Return whether the user accepted the currently active T&C version."""
    terms = (user.user_settings or {}).get("terms") or {}
    return bool(terms.get("accepted_at")) and terms.get("version") == CURRENT_TERMS_VERSION


def record_terms_acceptance(user: User) -> None:
    """Persist acceptance of the current T&C version (no-op if already current)."""
    if user_has_accepted_current_terms(user):
        return
    settings = user.user_settings or {}
    settings["terms"] = {
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "version": CURRENT_TERMS_VERSION,
    }
    user.user_settings = settings

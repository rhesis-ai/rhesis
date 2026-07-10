"""Terms and Conditions acceptance tracking.

The login page requires users to accept the active T&C version before
authenticating. Acceptance is stored on the user record so returning users
are not prompted again until the version changes.

Bump ``CURRENT_TERMS_VERSION`` (and ``CURRENT_TERMS_EFFECTIVE_DATE``) when
publishing new terms; users with an older ``terms_accepted_version`` must
re-accept on next login.
"""

from datetime import date, datetime, timezone

from rhesis.backend.app.models.user import User

# Active T&C version shown on the login page (effective 2025-09-01).
CURRENT_TERMS_VERSION = "1.0"
CURRENT_TERMS_EFFECTIVE_DATE = date(2025, 9, 1)


def user_has_accepted_current_terms(user: User) -> bool:
    """Return whether the user accepted the currently active T&C version."""
    return (
        user.terms_accepted_at is not None and user.terms_accepted_version == CURRENT_TERMS_VERSION
    )


def record_terms_acceptance(user: User) -> None:
    """Persist acceptance of the current T&C version (no-op if already current)."""
    if user_has_accepted_current_terms(user):
        return
    user.terms_accepted_at = datetime.now(timezone.utc)
    user.terms_accepted_version = CURRENT_TERMS_VERSION

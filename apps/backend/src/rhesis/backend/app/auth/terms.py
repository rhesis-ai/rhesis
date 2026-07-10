"""Terms and Conditions acceptance tracking."""

from datetime import date, datetime, timezone

from rhesis.backend.app.models.user import User

CURRENT_TERMS_VERSION = "1.0"
CURRENT_TERMS_EFFECTIVE_DATE = date(2025, 9, 1)


def user_has_accepted_current_terms(user: User) -> bool:
    """Return True when the user accepted the currently active T&C version."""
    return (
        user.terms_accepted_at is not None
        and user.terms_accepted_version == CURRENT_TERMS_VERSION
    )


def record_terms_acceptance(user: User) -> None:
    """Persist acceptance of the current T&C version for a user."""
    user.terms_accepted_at = datetime.now(timezone.utc)
    user.terms_accepted_version = CURRENT_TERMS_VERSION

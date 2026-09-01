"""Terms and Conditions acceptance tracking.

New users accept the active T&C version during onboarding (step 0). Acceptance
is stored in ``user_settings.terms`` (``version`` + ``accepted_at``) so they
are not prompted again until the version changes.

Existing onboarded users without a terms record are backfilled once at deploy
by alembic revision ``b5c6d7e8f9a0`` (baseline version ``1.0``). After that,
only an explicit accept or a version bump matters.

Bump ``CURRENT_TERMS_VERSION`` (and ``CURRENT_TERMS_EFFECTIVE_DATE``) when
publishing new terms; users with an older accepted version must
re-accept before continuing. ``TermsAcceptanceGate`` on the frontend reads
``has_prior_acceptance`` and shows such a user "Updated Terms" rather than
first-run copy, so a bump needs no frontend change.

**Do not bump this ahead of the terms themselves being published.** The
consent dialog links to rhesis.ai for the document, so a version live here
before the page is live means users accepting a version number whose text
they cannot yet read -- and the acceptance record would point at the wrong
document.
"""

from datetime import date, datetime, timezone

from rhesis.backend.app.models.user import User

# Active T&C version.
#
# 2.0 replaces the public preview terms with the commercial SaaS terms and
# conditions, published at rhesis.ai/terms-conditions/saas. A major bump
# because it is a different document rather than an amendment: the preview
# terms said of themselves that they would be replaced once a commercial
# offering existed, and Free is now designated a Free Trial Phase under
# Section 14 rather than being uncovered. Everyone carrying 1.0 -- including
# the users the ``b5c6d7e8f9a0`` backfill set to that baseline -- is prompted
# to re-accept on their next request.
#
# The version is ours, not the document's: the SaaS terms are issued as an
# appendix and carry no version of their own.
CURRENT_TERMS_VERSION = "2.0"
CURRENT_TERMS_EFFECTIVE_DATE = date(2026, 9, 1)


def _user_terms(user: User) -> dict:
    return (user.user_settings or {}).get("terms") or {}


def user_has_accepted_current_terms(user: User) -> bool:
    """Return whether the user accepted the currently active T&C version."""
    terms = _user_terms(user)
    return bool(terms.get("accepted_at")) and terms.get("version") == CURRENT_TERMS_VERSION


def user_has_prior_terms_acceptance(user: User) -> bool:
    """Return whether the user accepted any T&C version (possibly outdated)."""
    return bool(_user_terms(user).get("accepted_at"))


def record_terms_acceptance(user: User) -> None:
    """Persist acceptance of the current T&C version (no-op if already current)."""
    if user_has_accepted_current_terms(user):
        return
    settings = dict(user.user_settings or {})
    settings["terms"] = {
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "version": CURRENT_TERMS_VERSION,
    }
    user.user_settings = settings

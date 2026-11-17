"""When an unverified email address stops being allowed in.

A password sign-up proves nothing about the address, so the account gets
``EMAIL_VERIFICATION_GRACE`` to click the link in the verification mail. After
that, or as soon as mail to the address hard-bounces, the account can't sign
in or call the API until it verifies. OAuth, SSO and magic-link accounts are
verified when they sign in, so they never carry a deadline.

None of this applies without SMTP: the verification mail can't be sent, so a
self-hosted instance with no mail server would otherwise lock everyone out.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from rhesis.backend.app.config.settings import get_smtp_settings
from rhesis.backend.app.models.user import User

EMAIL_VERIFICATION_GRACE = timedelta(days=3)

#: 403 ``detail`` values; the frontend matches on them to pick the message.
EMAIL_NOT_VERIFIED = "email_not_verified"
EMAIL_UNDELIVERABLE = "email_undeliverable"


def verification_enforced() -> bool:
    """Whether this instance can send the verification mail at all."""
    settings = get_smtp_settings()
    return bool(settings.host and settings.user and settings.password)


def verification_deadline(now: Optional[datetime] = None) -> datetime:
    """The deadline a fresh password sign-up gets."""
    return (now or datetime.now(timezone.utc)) + EMAIL_VERIFICATION_GRACE


def verification_lapsed(user: User, now: Optional[datetime] = None) -> bool:
    """Whether this account is locked out until it verifies its email."""
    if user.is_email_verified or user.email_verification_due_at is None:
        return False
    if not verification_enforced():
        return False
    if user.email_bounced_at is not None:
        return True
    return (now or datetime.now(timezone.utc)) >= user.email_verification_due_at


def refuse_if_verification_lapsed(user: User) -> None:
    if not verification_lapsed(user):
        return
    # Only reached after the caller proved who they are, so naming the bounce leaks nothing.
    detail = EMAIL_UNDELIVERABLE if user.email_bounced_at is not None else EMAIL_NOT_VERIFIED
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_verified_email(user: User) -> None:
    """For actions that mail other people (invites): no grace period."""
    if user.is_email_verified or not verification_enforced():
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verify your email address before inviting members.",
    )

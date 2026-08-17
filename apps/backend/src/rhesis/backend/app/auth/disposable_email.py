"""Disposable email domain screening for self-serve sign-up.

Applies to the three paths where a visitor creates their own account
(password register, magic link, OAuth first login). Admin invites are
deliberately not screened — an operator inviting a colleague has already
vetted the address.
"""

import logging
from functools import lru_cache
from pathlib import Path

from disposable_email_domains import blocklist as _upstream_blocklist
from email_validator import EmailNotValidError, validate_email

from rhesis.backend.app.config.settings import get_auth_settings
from rhesis.backend.app.utils.redact import redact_email

logger = logging.getLogger(__name__)

CUSTOM_DOMAINS_FILE = Path(__file__).parent / "disposable_domains_custom.txt"

REJECTION_MESSAGE = (
    "Disposable email addresses are not accepted. Please sign up with a permanent address."
)


class DisposableEmailError(ValueError):
    """Sign-up address matched a disposable-domain list while enforcement is on.

    Subclasses ValueError so call sites that already turn a bad address into a
    400 need no change; callers that want to skip the generic error logging
    catch this type instead.
    """


def _read_custom_domains() -> set[str]:
    """Read the in-repo supplement to the upstream list. Blank lines and # comments are skipped."""
    if not CUSTOM_DOMAINS_FILE.exists():
        return set()

    domains = set()
    for raw_line in CUSTOM_DOMAINS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip().lower()
        if line:
            domains.add(line)
    return domains


def _read_env_domains() -> set[str]:
    raw = get_auth_settings().disposable_email_extra_domains
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


@lru_cache(maxsize=1)
def get_blocklist() -> frozenset[str]:
    """Merged upstream + in-repo + env-override domain set."""
    merged = {domain.lower() for domain in _upstream_blocklist}
    merged |= _read_custom_domains()
    merged |= _read_env_domains()
    return frozenset(merged)


def match_domain(ascii_domain: str) -> str | None:
    """
    Return the blocklist entry matching this domain, or None.

    Strips labels left to right so `mail.tempmail.example` matches a
    `tempmail.example` entry — otherwise any subdomain bypasses the list.
    """
    labels = ascii_domain.lower().strip(".").split(".")
    blocklist = get_blocklist()
    # Stop at two labels; a one-label suffix would match every .com address
    # if a bare TLD ever slipped into the list.
    for index in range(len(labels) - 1):
        candidate = ".".join(labels[index:])
        if candidate in blocklist:
            return candidate
    return None


def _ascii_domain_of(email: str) -> str | None:
    """
    Punycode form of the email's domain.

    Matching has to happen on the ASCII domain: `validate_and_normalize_email`
    returns the Unicode form, so an IDN address would never match the
    punycode entries the upstream list stores.
    """
    try:
        return validate_email(email, check_deliverability=False).ascii_domain
    except EmailNotValidError:
        return None


def screen_signup_email(email: str, *, source: str) -> None:
    """
    Screen a self-serve sign-up address against the disposable-domain lists.

    Raises DisposableEmailError only in "enforce" mode; in "log" mode the match
    is recorded and the sign-up proceeds.
    """
    mode = get_auth_settings().block_disposable_emails
    if mode == "off":
        return

    ascii_domain = _ascii_domain_of(email)
    if ascii_domain is None:
        return

    matched = match_domain(ascii_domain)
    if matched is None:
        return

    logger.warning(
        "Disposable sign-up domain matched: email=%s domain=%s matched=%s source=%s mode=%s",
        redact_email(email),
        ascii_domain,
        matched,
        source,
        mode,
    )

    if mode == "enforce":
        raise DisposableEmailError(REJECTION_MESSAGE)

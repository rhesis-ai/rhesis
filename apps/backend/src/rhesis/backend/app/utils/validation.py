"""
Validation utilities for the application.
"""

import os

import dns.resolver
from email_validator import EmailNotValidError, validate_email

# Our clusters forward all rhesis.ai DNS queries to an internal BIND9 server that only
# knows the app's own hostnames (see kubernetes/base/internal-dns), so it has no MX
# record for the rhesis.ai apex. That makes the deliverability check below reject
# @rhesis.ai invites even though the domain has valid public MX records. Route this
# check through public resolvers to bypass that internal-only redirect.
#
# email_validator only applies its own DEFAULT_TIMEOUT (15s) when no dns_resolver is
# passed in, so a custom resolver needs an explicit lifetime or it falls back to
# dnspython's raw default. The deliverability check can chain up to four lookups
# (MX, then A/AAAA/TXT fallbacks), so an unbounded resolver could add many seconds
# to a single invite request if egress to these nameservers is blocked.
_DELIVERABILITY_DNS_RESOLVER = dns.resolver.Resolver(configure=False)
_DELIVERABILITY_DNS_RESOLVER.nameservers = os.environ.get(
    "EMAIL_DELIVERABILITY_DNS_SERVERS", "8.8.8.8,1.1.1.1"
).split(",")
_DELIVERABILITY_DNS_RESOLVER.lifetime = 3.0


def validate_and_normalize_email(email: str, check_deliverability: bool = False) -> str:
    """
    Validate and normalize an email address.

    Args:
        email: The email address to validate and normalize
        check_deliverability: If True, verify the domain has valid MX records
            that can receive email. Use for user creation/invitations to catch
            typos and fake domains. Defaults to False for fast validation in
            login/lookup flows.

    Returns:
        str: The normalized email address

    Raises:
        ValueError: If the email is invalid or the domain cannot receive email
    """
    if not email or not email.strip():
        raise ValueError("Email address is required")

    try:
        validated_email = validate_email(
            email.strip(),
            check_deliverability=check_deliverability,
            dns_resolver=_DELIVERABILITY_DNS_RESOLVER if check_deliverability else None,
        )
        return validated_email.normalized
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email address: {str(e)}")


def is_valid_email(email: str) -> bool:
    """
    Check if an email address is valid without raising an exception.

    Args:
        email: The email address to check

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        validate_and_normalize_email(email)
        return True
    except ValueError:
        return False

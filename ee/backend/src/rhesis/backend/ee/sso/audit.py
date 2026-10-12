"""Structured log lines for SSO events, for incident forensics.

The audit log records the same moments for orgs that have it: a sign-in as
``session.signed_in`` (``record_user_event`` in the SSO router), a rejected
sign-in by an account in the org as its failure (``record_failed_sign_in``),
and config changes and provisioning as the ``organization`` and ``member``
row changes they are. These lines stay because they also cover what the
audit log does not: initiated logins, IdP errors, and people with no account.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("rhesis.sso.audit")


class SSOAuditEvent(str, Enum):
    CONFIG_CREATED = "sso.config.created"
    CONFIG_UPDATED = "sso.config.updated"
    CONFIG_DELETED = "sso.config.deleted"
    LOGIN_INITIATED = "sso.login.initiated"
    LOGIN_SUCCESS = "sso.login.success"
    LOGIN_FAILED = "sso.login.failed"
    USER_PROVISIONED = "sso.user.provisioned"
    USER_REJECTED = "sso.user.rejected"


def audit_log(
    event: SSOAuditEvent,
    org_id: str,
    *,
    email: Optional[str] = None,
    actor_id: Optional[str] = None,
    reason_code: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Emit a structured SSO audit log entry.

    All fields are safe to log (no secrets, no tokens).
    """
    entry: dict = {
        "event": event.value,
        "org_id": org_id,
    }
    if email:
        entry["email"] = email
    if actor_id:
        entry["actor_id"] = actor_id
    if reason_code:
        entry["reason_code"] = reason_code
    if details:
        entry["details"] = details

    logger.info("SSO_AUDIT: %s", entry)

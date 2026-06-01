"""Structured audit log for the API Clients feature.

Two event families share this module because they belong to the same
EE feature surface:

- :class:`AuthClientLifecycleEvent` -- create / rotate / disable /
  enable / delete on the per-org ``auth_client`` rows.
- :class:`TokenExchangeEvent` -- success / denial of an
  ``/auth/token-exchange`` request.

Forbidden fields (anywhere in audit output)
------------------------------------------
- raw email
- raw subject_token / access_token / refresh_token
- plaintext client_secret
- full client_secret_hash (logging only the first 8 chars when
  correlation is needed; the helper :func:`_truncate_hash_for_log`
  produces that form)

A regression test scans the captured log buffer after each event and
fails if any of the forbidden patterns appear.

Email hashing
-------------
``hashed_email`` is **HMAC-SHA256(key=AUDIT_HASH_KEY, msg=email.lower())``,
hex-encoded -- *not* a raw SHA-256, which would be rainbow-table-able for
any known address. ``AUDIT_HASH_KEY`` lives in its own env var so it
can be rotated independently of ``JWT_SECRET_KEY``; rotating it
invalidates the ability to correlate old vs new events for the same
email, which is the intended privacy / forensics tradeoff.

The helper fails closed in non-dev environments when the key is
missing -- a missing audit hash key in production silently disables
forensic correlation, which is exactly the misconfiguration the audit
trail is supposed to defend against.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from enum import Enum
from typing import Optional

from rhesis.backend.app.config.settings import get_application_settings

logger = logging.getLogger("rhesis.api_clients.audit")


class AuthClientLifecycleEvent(str, Enum):
    """Audit events emitted by AuthClient CRUD endpoints."""

    CREATED = "auth_client.created"
    ROTATED = "auth_client.rotated"
    DISABLED = "auth_client.disabled"
    ENABLED = "auth_client.enabled"
    DELETED = "auth_client.deleted"


class TokenExchangeEvent(str, Enum):
    """Audit events emitted by ``POST /auth/token-exchange``."""

    SUCCESS = "token_exchange.success"
    DENIED = "token_exchange.denied"


# ---------------------------------------------------------------------------
# Email hashing for forensics
# ---------------------------------------------------------------------------


def _is_dev_environment() -> bool:
    """Mirror :func:`rhesis.backend.ee.sso.http_client.is_dev_environment`.

    Duplicated here rather than imported so this audit module has zero
    runtime dependency on the SSO subpackage; otherwise importing
    ``audit`` would transitively pull in ``httpx`` even in test setups
    that do not exercise SSO.
    """
    settings = get_application_settings()
    dev_environments = ("local", "development", "staging")
    return settings.backend_env in dev_environments


def _get_audit_hash_key() -> Optional[bytes]:
    """Return the configured AUDIT_HASH_KEY as bytes, or ``None``.

    In dev / test we tolerate a missing key (and emit ``None`` from
    :func:`hashed_email`) so unit tests don't need to set yet another
    env var. The startup-time check in EE bootstrap fails loud in
    production when the key is absent.
    """
    raw = os.getenv("AUDIT_HASH_KEY")
    if not raw:
        if not _is_dev_environment():
            # Should never reach here in production because EE bootstrap
            # asserts the key is set before registering API_CLIENTS.
            # Logged once so operators see it if the assertion is
            # misconfigured.
            logger.error(
                "AUDIT_HASH_KEY is not configured in a non-dev environment; "
                "audit events will not include hashed_email"
            )
        return None
    return raw.encode()


def hashed_email(email: Optional[str]) -> Optional[str]:
    """HMAC-SHA256 the lowercased email; return the hex digest, or ``None``.

    Returning ``None`` (and not the empty string) signals "no email was
    associated with this event" rather than "the empty email" so the
    audit log can distinguish the two cases. The digest is stable
    across calls within a single ``AUDIT_HASH_KEY``: rotating the key
    is the deliberate way to break long-term correlation.
    """
    if not email:
        return None
    key = _get_audit_hash_key()
    if key is None:
        return None
    msg = email.strip().lower().encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Hash truncation for log correlation
# ---------------------------------------------------------------------------


def _truncate_hash_for_log(value: Optional[str], chars: int = 8) -> Optional[str]:
    """Return at most *chars* characters of *value* for log correlation.

    Used when we want to correlate two log lines about the same
    secret hash without ever printing the full hash. Eight hex chars
    of a SHA-256 output = 32 bits of distinguishing power, which:

    - is enough to grep through a single tenant's lifecycle events
      without collisions in any realistic volume (creates / rotates
      are sparse compared to token-exchange traffic),
    - is *not* enough to materially help offline brute force: each
      additional bit doubles attacker work, but the input alphabet
      (a 256-bit Fernet ciphertext over a versioned hash string) has
      effectively no exploitable structure either way.

    A 4-char (16-bit) prefix would still be useful for correlation
    but starts colliding around ~256 entries (birthday bound), which
    is uncomfortably close to the operational scale of a busy org.
    """
    if not value:
        return None
    return value[:chars]


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------


def auth_client_audit_log(
    event: AuthClientLifecycleEvent,
    org_id: str,
    *,
    client_id: str,
    actor_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    secret_hash_for_correlation: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Emit a structured AUTH_CLIENT lifecycle audit log entry.

    Hand-curated allowlist of fields. Any new context belongs in
    *details* so an at-a-glance review of this signature confirms
    nothing sensitive can leak by accident.
    """
    entry: dict = {
        "event": event.value,
        "org_id": org_id,
        "client_id": client_id,
    }
    if actor_id:
        entry["actor_id"] = actor_id
    if ip:
        entry["ip"] = ip
    if user_agent:
        entry["user_agent"] = user_agent
    if secret_hash_for_correlation:
        entry["secret_hash_prefix"] = _truncate_hash_for_log(
            secret_hash_for_correlation
        )
    if details:
        entry["details"] = details

    logger.info("API_CLIENT_AUDIT: %s", entry)


def token_exchange_audit_log(
    event: TokenExchangeEvent,
    *,
    org_id: Optional[str],
    client_id: Optional[str],
    iss: Optional[str] = None,
    subject_token_jti: Optional[str] = None,
    email: Optional[str] = None,
    scope: Optional[str] = None,
    reason_code: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Emit a structured TOKEN_EXCHANGE audit log entry.

    The function is the only sanctioned exit point for token-exchange
    audit data. ``email`` is hashed via :func:`hashed_email` before
    serialization; raw email never reaches the log buffer.

    Fields that are explicitly **not** parameters (and therefore
    cannot leak even by mistake): ``subject_token`` (raw),
    ``access_token`` (raw issued JWT), ``refresh_token`` (raw),
    ``client_secret``, ``client_secret_hash``.
    """
    entry: dict = {
        "event": event.value,
    }
    if org_id is not None:
        entry["org_id"] = org_id
    if client_id is not None:
        entry["client_id"] = client_id
    if iss is not None:
        entry["iss"] = iss
    if subject_token_jti is not None:
        entry["subject_token_jti"] = subject_token_jti
    he = hashed_email(email)
    if he is not None:
        entry["hashed_email"] = he
    if scope is not None:
        entry["scope"] = scope
    if reason_code is not None:
        entry["reason_code"] = reason_code
    if ip is not None:
        entry["ip"] = ip
    if user_agent is not None:
        entry["user_agent"] = user_agent

    logger.info("TOKEN_EXCHANGE_AUDIT: %s", entry)


__all__ = [
    "AuthClientLifecycleEvent",
    "TokenExchangeEvent",
    "auth_client_audit_log",
    "hashed_email",
    "token_exchange_audit_log",
]

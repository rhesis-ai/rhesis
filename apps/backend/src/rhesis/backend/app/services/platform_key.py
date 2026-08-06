"""Org-scoped Rhesis platform API key management (local/self-hosted mode).

Stores an encrypted Rhesis platform API key on the organization row so
self-hosted deployments can configure the hosted-model key per organization
via REST instead of only through the ``RHESIS_API_KEY`` env var.

Security invariants:
- The raw key is never returned by any status helper and never logged.
- It is stored encrypted at rest via the ``EncryptedString`` column type.
- Validation is best-effort and must never raise on network errors.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_rhesis_settings
from rhesis.backend.app.models.organization import Organization

logger = logging.getLogger(__name__)

# Keep probes short so status reads stay cheap even when the platform is slow
# or unreachable.
_VALIDATION_TIMEOUT_SECONDS = 5.0

# How long a cached validation result is trusted before an opt-in refresh
# (GET /platform/rhesis-key with refresh=True) will re-probe. GET /models never
# refreshes -- it always reads the cache.
_CACHE_TTL_SECONDS = 600  # 10 minutes

# Default hosted Polyphemus URL, mirrored from the SDK provider so the backend
# does not need to import the SDK just to read a constant.
_DEFAULT_POLYPHEMUS_URL = "https://polyphemus.rhesis.ai"


def _load_org(db: Session, organization_id) -> Organization | None:
    """Load the organization row.

    ``Organization`` is exempt from the ambient tenant auto-filter (it is
    queried before any tenant context exists), so a direct ``id`` lookup is
    the correct pattern here -- mirroring ``feature_gates._load_org`` and
    ``crud.get_organization``. Callers pass the authenticated user's own
    ``organization_id``, which keeps access org-scoped.
    """
    if not organization_id:
        return None
    return db.query(Organization).filter(Organization.id == organization_id).first()


def _resolve_key(org: Organization | None) -> str | None:
    """Resolve the effective platform key from a loaded org row (no query).

    Prefers the org-stored (encrypted) key; falls back to the process-wide
    ``RHESIS_API_KEY`` env var when the org has none. An empty string counts
    as "not set". Returns ``None`` when neither source provides a key.
    """
    stored = org.rhesis_api_key if org else None
    if stored:  # non-empty stored key wins
        return stored
    env_key = get_rhesis_settings().api_key
    return env_key or None


def get_platform_api_key(db: Session, organization_id) -> str | None:
    """Return the effective Rhesis platform API key for the organization.

    Single source of truth for "is a platform key present": prefers the
    org-stored (encrypted) key and falls back to the process-wide
    ``RHESIS_API_KEY`` env var. Cheap: one row read plus an env lookup, no
    network. Returns ``None`` when neither source provides a key.
    """
    return _resolve_key(_load_org(db, organization_id))


def is_platform_key_present(db: Session, organization_id) -> bool:
    """Whether ANY platform key is resolvable for the organization.

    True when either the org has a stored key OR the process-wide
    ``RHESIS_API_KEY`` env var is set -- i.e. exactly when model resolution
    (``get_platform_api_key``) would find a key to authenticate with. This is
    the presence check that drives both the availability annotation's
    ``rhesis_key_missing`` decision and the ``configured`` status field.
    """
    return bool(get_platform_api_key(db, organization_id))


def get_cached_polyphemus_authorized(db: Session, organization_id) -> bool | None:
    """Return the cached Polyphemus authorization for the org (pure read).

    Reads the persisted validation result only -- no network call and no
    commit -- so it is safe on the GET /models hot path. ``None`` means the
    result is unknown / not yet validated (fail-open at the call site).
    """
    org = _load_org(db, organization_id)
    return org.rhesis_key_polyphemus_authorized if org else None


def get_cached_key_valid(db: Session, organization_id) -> bool | None:
    """Return the cached validity of the org's platform key (pure read).

    Reads the persisted validation result only -- no network call and no
    commit -- so it is safe on the GET /models hot path. ``None`` means the
    result is unknown / not yet validated (fail-open at the call site: a key
    that has never been probed, e.g. an ``RHESIS_API_KEY`` env key on a
    deployment that never opened the platform settings, is not treated as
    invalid).
    """
    org = _load_org(db, organization_id)
    return org.rhesis_key_valid if org else None


def get_availability_signals(db: Session, organization_id) -> dict:
    """Return presence + cached validation signals from a single org lookup.

    Equivalent to calling ``is_platform_key_present``, ``get_cached_key_valid``,
    and ``get_cached_polyphemus_authorized`` individually, but loads the
    organization row once instead of three times -- for callers on a hot path
    (e.g. the GET /models availability annotation) that need all three signals
    together.
    """
    org = _load_org(db, organization_id)
    return {
        "present": bool(_resolve_key(org)),
        "key_valid": org.rhesis_key_valid if org else None,
        "polyphemus_authorized": org.rhesis_key_polyphemus_authorized if org else None,
    }


def set_platform_api_key(db: Session, organization_id, key: str) -> None:
    """Store *key* (encrypted) on the organization row and cache its status.

    Refresh-on-write: this is a write endpoint, so it probes the key once
    (``validate_platform_key``) and persists the validation result alongside
    the key. Subsequent status reads and the GET /models availability
    annotation then read those cached columns instead of re-probing.
    """
    org = _load_org(db, organization_id)
    if org is None:
        raise ValueError("Organization not found")
    org.rhesis_api_key = key
    validation = validate_platform_key(key)
    org.rhesis_key_valid = validation["valid"]
    org.rhesis_key_polyphemus_authorized = validation["polyphemus_authorized"]
    org.rhesis_key_last_checked_at = datetime.now(timezone.utc)
    db.commit()


def clear_platform_api_key(db: Session, organization_id) -> None:
    """Remove any stored platform key from the organization row.

    Nulls the key and all cached validation state. Note this clears only the
    DB-stored key; if a process-wide ``RHESIS_API_KEY`` env var remains, the
    key stays *present* (``configured`` correctly reports ``True``).
    """
    org = _load_org(db, organization_id)
    if org is None:
        return
    org.rhesis_api_key = None
    org.rhesis_key_valid = None
    org.rhesis_key_polyphemus_authorized = None
    org.rhesis_key_last_checked_at = None
    db.commit()


def _probe_polyphemus_authorized(key: str) -> bool | None:
    """Best-effort fallback: probe Polyphemus to infer authorization.

    Only an *auth-enforcing* response is conclusive: a ``401``/``403`` proves
    the token was rejected (``False``). Any other status -- including a ``200``
    from a public root/health endpoint -- does NOT prove the token was
    accepted, so it is inconclusive and returns ``None`` (fail-open at the call
    site). Never raises.
    """
    base_url = (os.getenv("DEFAULT_POLYPHEMUS_URL") or _DEFAULT_POLYPHEMUS_URL).rstrip("/")
    try:
        resp = httpx.get(
            base_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=_VALIDATION_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # network / DNS / timeout -- undeterminable
        logger.warning("Polyphemus authorization probe failed: %s", exc)
        return None
    if resp.status_code in (401, 403):
        return False
    # A non-auth-enforcing response (e.g. a public 200 root) cannot be
    # attributed to the Bearer token being valid -- treat as inconclusive.
    return None


def validate_platform_key(key: str) -> dict:
    """Best-effort validation of a Rhesis platform API key.

    Returns ``{"valid": bool | None, "polyphemus_authorized": bool | None}``.
    Never raises: unknowns (network errors, unexpected responses) map to
    ``None``. Polyphemus authorization is derived from the key owner's
    ``is_verified`` flag (the platform's admin/Polyphemus access gate),
    queried from the hosted platform's ``/users/settings`` endpoint; if that
    is inconclusive, a lightweight Polyphemus probe is used as a fallback.
    """
    result: dict = {"valid": None, "polyphemus_authorized": None}
    if not key:
        return {"valid": False, "polyphemus_authorized": False}

    base_url = get_rhesis_settings().base_url.rstrip("/")
    try:
        resp = httpx.get(
            f"{base_url}/users/settings",
            headers={"Authorization": f"Bearer {key}"},
            timeout=_VALIDATION_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # network / DNS / timeout -- cannot determine validity
        logger.warning("Platform key validation request failed: %s", exc)
        result["polyphemus_authorized"] = _probe_polyphemus_authorized(key)
        return result

    if resp.status_code in (401, 403):
        return {"valid": False, "polyphemus_authorized": False}
    if resp.status_code >= 400:
        # Server-side or unexpected error: key validity is undeterminable.
        result["polyphemus_authorized"] = _probe_polyphemus_authorized(key)
        return result

    result["valid"] = True
    try:
        body = resp.json()
        is_verified = body.get("is_verified")
        result["polyphemus_authorized"] = (
            bool(is_verified) if is_verified is not None else _probe_polyphemus_authorized(key)
        )
    except Exception:
        result["polyphemus_authorized"] = _probe_polyphemus_authorized(key)
    return result


def _mask_key(key: str) -> str:
    """Return a masked representation exposing at most the last 4 characters."""
    tail = key[-4:] if len(key) >= 4 else key
    return f"…{tail}"


def _should_reprobe(org: Organization) -> bool:
    """Whether the cached validation is stale enough to re-probe (refresh mode).

    True when the key has never been validated or was last validated more than
    ``_CACHE_TTL_SECONDS`` ago, so the cache is honored within that window.
    """
    last = org.rhesis_key_last_checked_at
    if last is None:
        return True
    if last.tzinfo is None:  # treat naive timestamps as UTC
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() > _CACHE_TTL_SECONDS


def get_platform_key_status(db: Session, organization_id, refresh: bool = False) -> dict:
    """Return the org platform key status without ever exposing the raw key.

    Shape matches :class:`~rhesis.backend.app.schemas.platform.PlatformKeyStatus`.

    A PURE READ by default: it reads the cached validation columns and performs
    NO network call and NO commit, so it is safe on the GET /models hot path.

    ``refresh=True`` (used only by the GET /platform/rhesis-key endpoint) may
    re-probe and persist the result, but only when the cache is missing or
    older than ``_CACHE_TTL_SECONDS`` -- otherwise the cached values are honored.
    """
    org = _load_org(db, organization_id)
    resolved = _resolve_key(org)

    if refresh and resolved and org is not None and _should_reprobe(org):
        validation = validate_platform_key(resolved)
        org.rhesis_key_valid = validation["valid"]
        org.rhesis_key_polyphemus_authorized = validation["polyphemus_authorized"]
        org.rhesis_key_last_checked_at = datetime.now(timezone.utc)
        db.commit()

    last_checked = org.rhesis_key_last_checked_at if org else None
    return {
        "configured": bool(resolved),
        "valid": org.rhesis_key_valid if org else None,
        "polyphemus_authorized": org.rhesis_key_polyphemus_authorized if org else None,
        "masked_key": _mask_key(resolved) if resolved else None,
        "last_checked_at": last_checked.isoformat() if last_checked else None,
    }

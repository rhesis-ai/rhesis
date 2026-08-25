"""Org-scoped Rhesis platform API key management.

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

from rhesis.backend.app.config.settings import get_application_settings, get_rhesis_settings
from rhesis.backend.app.models.organization import Organization

#: Providers whose models depend on the Rhesis platform key when ENABLE_RHESIS_KEY is set.
_PLATFORM_PROVIDERS = ("rhesis", "polyphemus")

logger = logging.getLogger(__name__)

# Keep probes short so status reads stay cheap even when the platform is slow
# or unreachable. validate_platform_key can run this twice sequentially (the
# primary probe, then the Polyphemus fallback probe) in a sync route handler
# holding a DB session -- 3s caps that worst case around 6s instead of 10s.
_VALIDATION_TIMEOUT_SECONDS = 3.0

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
    ``crud.organization.get_organization``. Callers pass the authenticated user's own
    ``organization_id``, which keeps access org-scoped.

    Soft-deleted orgs are still excluded despite the plain ``db.query(...)``:
    ``models/soft_delete_events.py`` registers a global ``before_compile``
    listener that appends ``deleted_at IS NULL`` to every query against a
    model with that column, with no opt-in required.
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


def get_availability_signals(db: Session, organization_id) -> dict:
    """Return presence + cached validation signals from a single org lookup.

    Presence is true when either the org has a stored key OR the process-wide
    ``RHESIS_API_KEY`` env var is set -- i.e. exactly when model resolution
    (``get_platform_api_key``) would find a key to authenticate with. Validity
    and Polyphemus authorization are pure reads of the cached
    ``rhesis_key_valid`` / ``rhesis_key_polyphemus_authorized`` columns --
    ``None`` means unknown / not yet validated (fail-open at the call site).
    No network call and no commit, so this is safe on the GET /models hot
    path -- and a single org load, not three, for callers (e.g. the
    availability annotation) that need all three signals together.
    """
    org = _load_org(db, organization_id)
    return {
        "present": bool(_resolve_key(org)),
        "key_valid": org.rhesis_key_valid if org else None,
        "polyphemus_authorized": org.rhesis_key_polyphemus_authorized if org else None,
    }


def _provider_of(model) -> str | None:
    """Return a model's provider type value, guarding a missing provider_type."""
    provider_type = getattr(model, "provider_type", None)
    return getattr(provider_type, "type_value", None) if provider_type else None


def annotate_model_availability(db: Session, organization_id, models_list) -> None:
    """Attach transient ``available``/``availability_reason`` attrs to ORM models.

    Read by Pydantic (``from_attributes=True``) at serialization time. Platform
    key state is computed ONCE per request, never per model, and this helper
    performs ZERO network calls and ZERO commits (safe on the GET /models hot
    path):

    - With ENABLE_RHESIS_KEY unset every model is available (no requirement
      change on deployments that don't use the platform key).
    - When enabled, presence is the cheap ``get_availability_signals`` check
      (DB-stored key OR the ``RHESIS_API_KEY`` env var -- same source the model
      resolver authenticates with), which loads the organization row once and
      returns presence plus the cached ``rhesis_key_valid`` /
      ``rhesis_key_polyphemus_authorized`` columns (populated on key writes and
      refreshes), never probed here. An unknown/None validity or authorization
      fails open (available=True) so an unprobed ``RHESIS_API_KEY`` env key is
      never greyed.

    Precedence when a platform key is present: a known-invalid key greys ALL
    rhesis/polyphemus models (including the defaults -- they cannot
    authenticate either), which takes priority over the narrower
    Polyphemus-authorization reason.

    Reason slugs are a frozen contract: ``"rhesis_key_missing"``,
    ``"rhesis_key_invalid"`` and ``"polyphemus_not_authorized"``.
    """
    if not get_application_settings().enable_rhesis_key:
        for model in models_list:
            model.available = True
            model.availability_reason = None
        return

    signals = get_availability_signals(db, organization_id)
    present = signals["present"]
    key_valid = signals["key_valid"]  # unknown => fail-open
    poly_authorized = signals["polyphemus_authorized"]  # unknown => fail-open

    for model in models_list:
        provider = _provider_of(model)
        if provider not in _PLATFORM_PROVIDERS:
            model.available = True
            model.availability_reason = None
        elif not present:
            model.available = False
            model.availability_reason = "rhesis_key_missing"
        elif key_valid is False:
            model.available = False
            model.availability_reason = "rhesis_key_invalid"
        elif provider == "polyphemus" and poly_authorized is False:
            model.available = False
            model.availability_reason = "polyphemus_not_authorized"
        else:
            model.available = True
            model.availability_reason = None


def set_platform_api_key(db: Session, organization_id, key: str) -> dict:
    """Store *key* (encrypted) on the organization row and return its status.

    Refresh-on-write: this is a write endpoint, so it probes the key once
    (``validate_platform_key``) and persists the validation result alongside
    the key. Subsequent status reads and the GET /models availability
    annotation then read those cached columns instead of re-probing.

    Returns the resulting status computed from the already-loaded, already-
    mutated org row -- callers don't need a separate ``get_platform_key_status``
    call (and its own org re-query) just to see the result of this write.

    Raises:
        ValueError: if no organization matches ``organization_id``.
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
    return _status_from_org(org)


def clear_platform_api_key(db: Session, organization_id) -> dict:
    """Remove any stored platform key from the organization row and return its status.

    Nulls the key and all cached validation state. Note this clears only the
    DB-stored key; if a process-wide ``RHESIS_API_KEY`` env var remains, the
    key stays *present* (``configured`` correctly reports ``True``).

    Returns the resulting status computed from the already-loaded row, same
    rationale as ``set_platform_api_key``. When no organization matches,
    returns the "nothing configured" status rather than raising -- clearing a
    key that can't be found is a no-op, not an error.
    """
    org = _load_org(db, organization_id)
    if org is None:
        return _status_from_org(None)
    org.rhesis_api_key = None
    org.rhesis_key_valid = None
    org.rhesis_key_polyphemus_authorized = None
    org.rhesis_key_last_checked_at = None

    # If an env-var fallback key exists, validate it so the cached validation
    # reflects the actual key's validity (otherwise None fails open and models
    # that should be greyed stay available).
    fallback = get_rhesis_settings().api_key
    if fallback:
        validation = validate_platform_key(fallback)
        org.rhesis_key_valid = validation["valid"]
        org.rhesis_key_polyphemus_authorized = validation["polyphemus_authorized"]
        org.rhesis_key_last_checked_at = datetime.now(timezone.utc)

    db.commit()
    return _status_from_org(org)


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
            follow_redirects=True,
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
            follow_redirects=True,
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


def _status_from_org(org: Organization | None) -> dict:
    """Build the status dict (shape matches ``PlatformKeyStatus``) from an already-loaded org.

    No query: reads whatever is currently on the in-memory ``org`` row, so
    callers that just mutated and committed it see their own write reflected
    without a redundant re-fetch.
    """
    resolved = _resolve_key(org)
    stored = org.rhesis_api_key if org else None
    last_checked = org.rhesis_key_last_checked_at if org else None
    # Distinguishes a removable org key from the deployment's RHESIS_API_KEY,
    # which DELETE cannot touch -- the UI needs this to avoid offering a
    # "remove" that would silently do nothing.
    if stored:
        source = "organization"
    elif resolved:
        source = "environment"
    else:
        source = None
    return {
        "configured": bool(resolved),
        "source": source,
        "valid": org.rhesis_key_valid if org else None,
        "polyphemus_authorized": org.rhesis_key_polyphemus_authorized if org else None,
        "masked_key": _mask_key(resolved) if resolved else None,
        "last_checked_at": last_checked.isoformat() if last_checked else None,
    }


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

    return _status_from_org(org)

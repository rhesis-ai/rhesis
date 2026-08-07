"""License token minting — the issuer side.

This module is the single implementation of license signing. All entry points
(CLI, GitHub Action / Cloud Run Job, future self-service endpoint) call
:func:`mint_token`, :func:`issue`, or :func:`deliver_to_secret_manager` rather
than duplicating signing logic.

Design notes
------------
* **Private key never in the app runtime.** The running backend only holds
  public keys (for verification). The private key is mounted into the
  Cloud Run issuance job from Secret Manager via ``--set-secrets`` and is
  read here from :data:`~rhesis.backend.ee.licensing.entitlements.ENV_LICENSE_PRIVATE_KEY`.
  Missing or malformed key → immediate ``RuntimeError``. We never mint a
  nil/unsigned token.
* **Token-authoritative model.** :func:`mint_token` stamps the full entitlement
  payload into the ``lic`` claim; the running backend trusts the signed token
  as-is (no re-derivation from any catalog at request time). Custom
  feature/limit overrides let you issue one-off bespoke deals without a
  redeploy.
* **``issue`` is DB-coupled; ``mint_token`` is not.** Keep them separate so
  ``mint_token`` can be tested or reused without a database.
* **``sub="*"`` is mint-only.** Blanket tokens have no ``organization`` row to
  write to; they are delivered as the ``RHESIS_LICENSE`` env var on the backend
  service. :func:`issue` refuses blanket subjects.
* **Self-hosted deliveries have no DB to write to either.** A self-hosted
  customer's ``organization`` row lives in their own database, not ours.
  :func:`deliver_to_secret_manager` is the delivery path for that case: it
  writes the minted (always blanket) token to a GCP Secret Manager secret
  instead of printing it to a log an operator has to scrape.
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import jwt  # PyJWT
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from rhesis.backend.ee.licensing.entitlements import (
    BLANKET_SUBJECT,
    CLAIM_AUDIENCE,
    CLAIM_EXPIRY,
    CLAIM_ISSUED_AT,
    CLAIM_ISSUER,
    CLAIM_JWT_ID,
    CLAIM_LICENSE,
    CLAIM_SUBJECT,
    ENV_LICENSE_PRIVATE_KEY,
    LIC_ALL_FEATURES,
    LIC_FEATURES,
    LIC_LIMITS,
    LICENSE_ALGORITHM,
    LICENSE_AUDIENCE,
    LICENSE_ISSUER,
    LicenseEdition,
    LicenseStatus,
)
from rhesis.backend.ee.licensing.tiers import tier_to_lic_claim

logger = logging.getLogger(__name__)

# Default TTL used when callers don't specify one (365 days).
DEFAULT_TTL_DAYS = 365


# ---------------------------------------------------------------------------
# Private key loading
# ---------------------------------------------------------------------------


def _load_private_key() -> Ed25519PrivateKey:
    """Load the Ed25519 signing key from the environment.

    Reads :data:`~rhesis.backend.ee.licensing.entitlements.ENV_LICENSE_PRIVATE_KEY`.
    Accepts both raw PEM (starts with ``-----BEGIN``) and the same PEM
    base64-encoded (the format used by the infrastructure secret store).

    :raises RuntimeError: if the variable is absent, empty, not decodable, or
        not an Ed25519 private key. Callers must never mint with a missing or
        wrong-type key.
    """
    raw = os.environ.get(ENV_LICENSE_PRIVATE_KEY, "").strip()
    if not raw:
        raise RuntimeError(
            f"{ENV_LICENSE_PRIVATE_KEY} is not set. "
            "The private key must be provided to mint a license token."
        )

    if raw.startswith("-----"):
        pem_bytes = raw.encode()
    else:
        try:
            pem_bytes = base64.b64decode(raw)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to base64-decode {ENV_LICENSE_PRIVATE_KEY}: {exc}. "
                "Provide either a raw PEM string (starting with '-----BEGIN') "
                "or the PEM base64-encoded."
            ) from exc

    try:
        key = load_pem_private_key(pem_bytes, password=None)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load Ed25519 private key from {ENV_LICENSE_PRIVATE_KEY}: {exc}"
        ) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError(
            f"{ENV_LICENSE_PRIVATE_KEY} does not contain an Ed25519 private key "
            f"(got {type(key).__name__}). Only EdDSA (Ed25519) is supported."
        )
    return key


# ---------------------------------------------------------------------------
# Core minting — no database dependency
# ---------------------------------------------------------------------------


def mint_token(
    org_id: str,
    edition: LicenseEdition,
    status: LicenseStatus = LicenseStatus.ACTIVE,
    ttl_days: int = DEFAULT_TTL_DAYS,
    kid: str = "rhesis-prod-v1",
    *,
    custom_features: Optional[list[str]] = None,
    custom_limits: Optional[dict[str, Any]] = None,
) -> str:
    """Mint and sign a license JWT for *org_id*.

    Builds the ``lic`` claim from the tier catalog (:func:`~rhesis.backend.ee.licensing.tiers.tier_to_lic_claim`)
    and optionally overrides ``features`` and/or ``limits`` for bespoke deals.
    Signs the result with the Ed25519 private key loaded from
    :data:`~rhesis.backend.ee.licensing.entitlements.ENV_LICENSE_PRIVATE_KEY`.

    :param org_id: JWT ``sub`` — an org UUID or :data:`~rhesis.backend.ee.licensing.entitlements.BLANKET_SUBJECT`
        (``"*"``) for a blanket all-orgs license.
    :param edition: License tier; must be a sellable edition in the catalog.
    :param status: Billing status; defaults to :attr:`~rhesis.backend.ee.licensing.entitlements.LicenseStatus.ACTIVE`.
    :param ttl_days: Validity period from now.  Default: 365 days.
    :param kid: Key ID header — identifies which baked-in public key to verify
        against.  Use ``"rhesis-prod-v1"`` for production,
        ``"rhesis-nonprod-v1"`` for non-prod environments.
    :param custom_features: When set, overrides the tier-default feature list
        (a sorted list of :class:`~rhesis.backend.app.features.FeatureName`
        string values). Use for one-off bespoke deals.
    :param custom_limits: When set, overrides or extends the tier-default
        limits dict (e.g. ``{"seats": 200}``).
    :returns: Signed JWT string.
    :raises RuntimeError: if the private key is unavailable or invalid, or if
        *edition* is not a sellable tier.
    """
    private_key = _load_private_key()

    now = int(datetime.now(tz=timezone.utc).timestamp())
    exp = now + ttl_days * 86400
    jti = str(uuid.uuid4())

    lic_claim = tier_to_lic_claim(edition, status)

    if custom_features is not None:
        lic_claim[LIC_FEATURES] = sorted(custom_features)
        # If the caller explicitly provides a feature list, clear all_features
        # so the verifier treats this as a list-based entitlement, not a
        # blanket grant — unless they also want all_features (which would be
        # unusual but still valid; they can re-enable it via custom_limits).
        lic_claim[LIC_ALL_FEATURES] = False

    if custom_limits is not None:
        merged = dict(lic_claim.get(LIC_LIMITS) or {})
        merged.update(custom_limits)
        lic_claim[LIC_LIMITS] = merged

    payload: dict[str, Any] = {
        CLAIM_ISSUER: LICENSE_ISSUER,
        CLAIM_AUDIENCE: LICENSE_AUDIENCE,
        CLAIM_SUBJECT: org_id,
        CLAIM_ISSUED_AT: now,
        CLAIM_EXPIRY: exp,
        CLAIM_JWT_ID: jti,
        CLAIM_LICENSE: lic_claim,
    }

    token: str = jwt.encode(
        payload,
        private_key,
        algorithm=LICENSE_ALGORITHM,
        headers={"kid": kid},
    )
    logger.info(
        "Minted license token: edition=%s kid=%s jti=%s exp=%s",
        edition.value,
        kid,
        jti,
        datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
    )
    logger.debug("Minted license token sub=%s", org_id)
    return token


# ---------------------------------------------------------------------------
# Issuance — writes to the database
# ---------------------------------------------------------------------------


def issue(
    db: Any,
    org_id: str,
    edition: LicenseEdition,
    status: LicenseStatus = LicenseStatus.ACTIVE,
    ttl_days: int = DEFAULT_TTL_DAYS,
    kid: str = "rhesis-prod-v1",
    *,
    dry_run: bool = False,
    custom_features: Optional[list[str]] = None,
    custom_limits: Optional[dict[str, Any]] = None,
) -> str:
    """Mint a token and (unless *dry_run*) write it to ``organization.license``.

    Uses :func:`mint_token` for signing, then writes the result to the
    ``organization`` row for *org_id* via
    :func:`~rhesis.backend.app.database.bind_scope_to_session` so both the ORM
    auto-stamp/filter listeners and the RLS GUCs are satisfied.

    :param db: An active SQLAlchemy :class:`~sqlalchemy.orm.Session`.  The
        session must be writable and the DB role must satisfy the RLS policy
        (``INSERT``/``UPDATE`` on ``organization``).  Typically created from
        the app's :data:`~rhesis.backend.app.database.SessionLocal` with DB
        credentials from the standard ``DB_*`` env vars.
    :param org_id: Target org UUID.  Must correspond to an existing
        ``organization`` row.  Blanket subject ``"*"`` is rejected — blanket
        tokens should be deployed as the ``RHESIS_LICENSE`` env var, not
        written to a DB row.
    :param dry_run: When ``True``, mint and return the token but do not write
        to the database.
    :returns: The signed JWT string (whether or not it was written).
    :raises ValueError: if *org_id* is the blanket subject ``"*"``.
    :raises RuntimeError: if the private key is unavailable/invalid.
    :raises sqlalchemy.exc.NoResultFound: if the org row does not exist.
    """
    if org_id == BLANKET_SUBJECT:
        raise ValueError(
            "Blanket subject '*' cannot be issued to an organization row. "
            "Mint with mint_token() and deploy as the RHESIS_LICENSE env var instead."
        )

    token = mint_token(
        org_id,
        edition,
        status=status,
        ttl_days=ttl_days,
        kid=kid,
        custom_features=custom_features,
        custom_limits=custom_limits,
    )

    if dry_run:
        logger.info("Dry-run: token minted for org=%s but not written to the DB", org_id)
        return token

    from rhesis.backend.app.database import bind_scope_to_session
    from rhesis.backend.app.models.organization import Organization

    bind_scope_to_session(db, organization_id=org_id)

    org = db.query(Organization).filter(Organization.id == org_id).one()
    org.license = token
    db.commit()

    logger.info("Issued license token written to organization.license: org=%s", org_id)
    return token


# ---------------------------------------------------------------------------
# Secret Manager delivery — for self-hosted deployments (no DB to write to)
# ---------------------------------------------------------------------------


def deliver_to_secret_manager(token: str, *, project_id: str, secret_name: str) -> str:
    """Write *token* as a new version of an existing Secret Manager secret.

    For self-hosted deployments there is no ``organization`` row to write
    to (see :func:`issue`) — the token itself, handed to the customer, is
    the deliverable. Landing it in Secret Manager instead of a CLI/CI log
    keeps it inside an access-controlled, audit-logged store rather than a
    log stream that anyone with log-viewer permissions can read.

    The secret must already exist; this function only adds a version to
    it, so a typo in *secret_name* fails loudly instead of silently
    creating a stray secret. Authentication is Application Default
    Credentials — when running as a Cloud Run job, that's the job's own
    runtime service account, which needs ``roles/secretmanager.
    secretVersionAdder`` on *secret_name*. No credential is threaded
    through this function's arguments.

    :param token: The signed JWT to store. Never logged.
    :param project_id: GCP project containing the secret.
    :param secret_name: Short secret name (not the full
        ``projects/.../secrets/...`` resource path).
    :returns: The created version's resource name — safe to log, since it
        contains only the project/secret/version identifiers, never the
        secret payload.
    :raises RuntimeError: if the secret doesn't exist or the caller lacks
        permission to add a version.
    """
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}/secrets/{secret_name}"
    try:
        response = client.add_secret_version(
            request={"parent": parent, "payload": {"data": token.encode("utf-8")}}
        )
    except GoogleAPICallError as exc:
        raise RuntimeError(
            f"Failed to deliver license token to Secret Manager secret "
            f"'{secret_name}' in project '{project_id}': {exc}. Confirm the "
            "secret already exists and the caller holds "
            "roles/secretmanager.secretVersionAdder on it."
        ) from exc

    logger.info("Delivered license token to Secret Manager: %s", response.name)
    return response.name


__all__ = [
    "DEFAULT_TTL_DAYS",
    "deliver_to_secret_manager",
    "issue",
    "mint_token",
]

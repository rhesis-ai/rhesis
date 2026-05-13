"""Per-org :class:`AuthClient` ORM model and authentication helpers.

An :class:`AuthClient` is a long-lived credential that an external
application (for example br.AI.n) presents to Rhesis when calling
``POST /auth/token-exchange``. Each row belongs to exactly one
organization; an org-A client can never mint tokens for org B (defense
in depth: the orchestrator also checks this match in step 3 of the
exchange flow, and the row is FK'd to ``organization`` with
``ON DELETE CASCADE`` so disabling a tenant tears down their clients).

Storage
-------
Plaintext secrets are never persisted. The DB column
``client_secret_hash`` keeps a versioned hash string of the form
``"sha256:<64 hex>"`` -- the prefix lets us migrate to a different
hash function later (e.g. argon2id) without ambiguity. Plain SHA-256
is adequate here because the secret is generated server-side via
``secrets.token_urlsafe(32)`` (256 bits of CSPRNG output), which is
not brute-forceable; a slow KDF would only hurt request latency
without improving security.

The hash itself is wrapped in
:class:`~rhesis.backend.app.utils.encryption.EncryptedString` (Fernet,
keyed by ``DB_ENCRYPTION_KEY``) for defense in depth at rest. A
DB-only compromise -- a leaked backup, an SQL-injection read primitive
that cannot reach the encryption key -- yields ciphertext, not the
hash, so an attacker cannot even attempt offline brute-force on
candidate secrets without first acquiring the encryption key. Mirrors
the convention used by :class:`~rhesis.backend.app.models.token.Token`,
:class:`~rhesis.backend.app.models.endpoint.Endpoint`,
:class:`~rhesis.backend.app.models.tool.Tool`, and
:class:`~rhesis.backend.app.models.model.Model` for any column whose
contents must remain confidential at rest.

Authentication
--------------
:func:`authenticate_client` is the single sanctioned access path. It
fails closed and is hardened against the obvious oracles:

- Always runs a SHA-256 over a sentinel even when ``client_id`` is
  unknown (S4a) so the wall clock for "unknown client" is comparable
  to "wrong secret"; without this, a patient attacker can enumerate
  which ``client_id`` values exist per org via timing.
- Compares secret hashes with :func:`hmac.compare_digest` (S4) instead
  of ``==``, eliminating byte-by-byte timing leaks.
- A single log line shape for both "unknown client" and "wrong
  secret"; never logs which branch was taken.
- Disabled clients are rejected with the same shape as wrong-secret.

The CRUD router and the token-exchange orchestrator both call this
helper -- there is no other authentication path.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session, relationship

from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.utils.encryption import EncryptedString

logger = logging.getLogger(__name__)


# 32 bytes of fixed entropy used as the operand for the dummy SHA-256 we
# run on a missing ``client_id``. The value is irrelevant; what matters
# is that hashing happens, taking comparable time to the success path.
# Stored at module level so it is allocated once.
_DUMMY_HASH_INPUT = b"\x00" * 32

#: Hash prefix that identifies the algorithm used for
#: :attr:`AuthClient.client_secret_hash`. A versioned prefix lets us
#: rotate to a different KDF later (e.g. ``"argon2id:..."``) without
#: ambiguity in stored values.
SECRET_HASH_PREFIX = "sha256:"


class AuthClient(Base):
    """Per-organization OAuth2 client used by external integrations.

    See module docstring for the threat model and rationale.

    Notes on column choices:

    - ``allowed_scopes`` uses Postgres ``text[]`` (``ARRAY(Text)``)
      because we are Postgres-only and an array column makes the CHECK
      constraint that ``default_scope = ANY(allowed_scopes)`` trivial
      to express in pure SQL. Switching to a JSON column would force
      Python-side validation and lose the at-rest invariant.
    - ``token_epoch`` is the lever for **coarse revocation**. Bumping
      it invalidates every Rhesis JWT issued before that instant
      because :func:`verify_jwt_token` enforces ``iat >= epoch``. No
      DB lookup is needed at verify time; the comparison is against
      the integer ``epoch`` claim embedded in the JWT.
    - ``disabled`` is a soft-disable flag separate from the soft-delete
      ``deleted_at`` inherited from :class:`Base`. Soft-disable lets
      an admin pause an integration without losing audit history;
      hard delete is only allowed on already-disabled clients.
    - ``name`` is unique per-org (when set) so the UI table never
      surfaces two indistinguishable rows. ``client_id`` is unique
      per-org so two organizations may both have a ``brain`` client.
    """

    __tablename__ = "auth_client"

    organization_id = Column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        String(64),
        nullable=False,
        comment=(
            "Public client identifier. Pattern: ^[a-z0-9][a-z0-9_-]{2,63}$. "
            "Unique per-organization."
        ),
    )
    client_secret_hash = Column(
        EncryptedString(),
        nullable=False,
        comment=(
            "Versioned secret hash of the form 'sha256:<64-hex>', "
            "wrapped in EncryptedString (Fernet, DB_ENCRYPTION_KEY) for "
            "defense in depth at rest. Application-side comparison uses "
            "hmac.compare_digest on the decrypted hash. Plaintext "
            "secrets are never persisted."
        ),
    )
    expected_subject_azp = Column(
        String(255),
        nullable=False,
        comment=(
            "Required azp claim of the subject token (RFC 8693). "
            "This is the ONLY mitigation against attacker A3 -- a "
            "co-tenant integration replaying its own valid Keycloak "
            "token at our endpoint."
        ),
    )
    expected_subject_audience = Column(
        String(255),
        nullable=True,
        comment=(
            "Optional aud claim the subject token must contain on top of "
            "the azp check. Set when the configured IdP emits an aud."
        ),
    )
    name = Column(
        String(120),
        nullable=True,
        comment="Human-readable label shown in the org settings UI.",
    )
    allowed_scopes = Column(
        ARRAY(Text),
        nullable=False,
        comment=(
            "Set of scopes the client may request. v1 values: "
            "{'read','full','offline_access'}."
        ),
    )
    default_scope = Column(
        String(255),
        nullable=False,
        comment=(
            "Space-separated scope string applied when the caller omits "
            "the scope parameter. Must be a subset of allowed_scopes."
        ),
    )
    token_epoch = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment=(
            "Coarse revocation lever. Access tokens with iat < epoch are "
            "rejected by verify_jwt_token. Bumped on rotate / explicit "
            "revoke."
        ),
    )
    disabled = Column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
        comment="Soft-disable flag. Disabled clients fail invalid_client.",
    )

    organization = relationship(
        "Organization",
        primaryjoin=("AuthClient.organization_id == Organization.id"),
        foreign_keys=[organization_id],
    )

    __table_args__ = (
        # Partial unique index on (organization_id, client_id), scoped
        # to live rows. A plain UniqueConstraint would forbid even
        # soft-deleted rows from sharing the same client_id, which
        # means an org that disables their ``brain`` integration and
        # later wants to recreate it would hit a 409 forever (or,
        # worse, the operator would have to hard-delete the audit
        # trail). The partial index lets us re-create after
        # soft-delete while still preventing two LIVE rows with the
        # same id.
        Index(
            "uq_auth_client_org_client_active",
            "organization_id",
            "client_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "uq_auth_client_org_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where="name IS NOT NULL AND deleted_at IS NULL",
        ),
        CheckConstraint(
            "default_scope = ANY(allowed_scopes)",
            name="ck_auth_client_default_scope_allowed",
        ),
    )


# ---------------------------------------------------------------------------
# Secret generation + hashing
# ---------------------------------------------------------------------------


def generate_client_secret() -> str:
    """Generate a fresh client secret.

    256 bits of CSPRNG output, URL-safe base64 (no padding). The
    returned value is the **only** time the plaintext exists; it is
    handed to the caller once via the create / rotate response and
    immediately hashed for storage by :func:`hash_client_secret`.
    """
    return secrets.token_urlsafe(32)


def hash_client_secret(plaintext: str) -> str:
    """Hash a plaintext secret for at-rest storage.

    Returns a string of the form ``"sha256:<64 hex>"``. The version
    prefix lets the verifier route to a different algorithm later
    without an ambiguous ``Q?`` migration step.
    """
    return SECRET_HASH_PREFIX + hashlib.sha256(plaintext.encode()).hexdigest()


def _verify_secret_hash(presented: str, stored_hash: str) -> bool:
    """Constant-time check of *presented* against *stored_hash*.

    Returns ``False`` if the stored hash uses an algorithm we do not
    recognise (forward compatibility: an unknown prefix is a hard fail,
    never a silent success).
    """
    if not stored_hash.startswith(SECRET_HASH_PREFIX):
        logger.warning(
            "Unknown client_secret_hash prefix; rejecting (hash starts %s)",
            stored_hash[:8],
        )
        return False

    candidate = hash_client_secret(presented)
    return hmac.compare_digest(candidate, stored_hash)


# ---------------------------------------------------------------------------
# Lookup + authentication
# ---------------------------------------------------------------------------


def authenticate_client(
    db: Session,
    organization_id,
    client_id: str,
    presented_secret: str,
) -> Optional[AuthClient]:
    """Authenticate a presented ``client_id`` / ``client_secret`` pair.

    Returns the :class:`AuthClient` on success and ``None`` on every
    failure mode. The function is the single sanctioned authentication
    primitive for both ``/auth/token-exchange`` and ``/auth/refresh``
    when the refresh row carries a ``client_id``.

    Hardening (each item maps to a security requirement in the plan):

    - **S4a (constant-time lookup):** if ``(org, client_id)`` does not
      resolve we still hash :data:`_DUMMY_HASH_INPUT` so the wall
      clock is comparable to the success path. Without this, an
      attacker can enumerate which clients exist by measuring response
      time.
    - **S4 (constant-time compare):** the hash comparison goes through
      :func:`hmac.compare_digest`, never ``==``.
    - **Single log shape:** unknown client / wrong secret / disabled
      all log the same warning; we never tell the caller (or the log
      reader) which branch fired. Per-branch debug logs would
      reintroduce the oracle the rest of the function works to remove.
    - **Org-scoped lookup:** the unique constraint on ``auth_client``
      is ``(organization_id, client_id)``, so two orgs may legitimately
      have the same ``client_id`` (e.g. ``brain``). Looking up by
      ``client_id`` alone would return whichever row sorts first and
      lock the other org out of token exchange. The caller passes the
      org resolved from the request's ``audience`` parameter (or, on
      the refresh path, from the bound user / client row) so this
      function authenticates against the correct row even under
      identifier collision across tenants.
    """

    row: Optional[AuthClient] = (
        db.query(AuthClient)
        .filter(
            AuthClient.organization_id == organization_id,
            AuthClient.client_id == client_id,
            AuthClient.deleted_at.is_(None),
        )
        .first()
    )

    if row is None:
        # Burn the same CPU we would have burned on a real verify so
        # the unknown-client branch is timing-indistinguishable from
        # the wrong-secret branch. The result is discarded.
        hashlib.sha256(_DUMMY_HASH_INPUT).hexdigest()
        hmac.compare_digest(
            "sha256:" + "0" * 64,
            "sha256:" + "1" * 64,
        )
        logger.warning("auth_client authentication failed")
        return None

    if not _verify_secret_hash(presented_secret, row.client_secret_hash):
        logger.warning("auth_client authentication failed")
        return None

    if row.disabled:
        # Same log shape, same return, so disabled-vs-wrong-secret is
        # not a public oracle either. The org admin already sees the
        # disabled state in the UI.
        logger.warning("auth_client authentication failed")
        return None

    return row


__all__ = [
    "AuthClient",
    "SECRET_HASH_PREFIX",
    "authenticate_client",
    "generate_client_secret",
    "hash_client_secret",
]

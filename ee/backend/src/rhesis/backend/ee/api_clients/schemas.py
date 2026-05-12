"""Pydantic schemas for the API Clients CRUD surface.

Two shapes share the model file because they belong to the same admin
workflow but the security-relevant difference between them is what
makes the contract correct:

- :class:`AuthClientCreatedResponse` is the **only** schema that
  carries the plaintext ``client_secret`` field. It is returned exactly
  once -- on create or rotate -- so the org admin can hand the secret
  to the integration owner via a secure channel. The frontend shows
  it once with an unambiguous warning and never persists it.
- :class:`AuthClientResponse` is the read-side shape used by every
  other route (list, get, after disable / enable). It physically lacks
  the ``client_secret`` field, so even a future bug that calls
  ``model_dump()`` on a freshly-created row cannot leak the secret
  through this schema.

A regression test asserts that ``AuthClientResponse.model_json_schema()``
contains neither ``client_secret`` nor ``client_secret_hash`` keys, so
a later edit cannot quietly add one back.

Validation
----------
Field-level validators here enforce the constraints called out in the
plan:

- ``client_id`` matches ``^[a-z0-9][a-z0-9_-]{2,63}$``.
- ``allowed_scopes`` are a subset of :data:`V1_SUPPORTED_SCOPES`.
- ``default_scope`` (a single token) is in ``allowed_scopes``.
- ``expected_subject_azp`` is non-empty (S1 -- this is the only
  control that prevents a co-tenant integration from replaying its
  own valid Keycloak token at our endpoint).

URL slug existence (the ``audience=rhesis:org:<slug>`` parameter
needs the parent ``Organization.slug`` to be non-null) is validated at
the router layer because it depends on the DB-loaded org, not on the
inbound request body.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: Coarse v1 scope set. ``read`` and ``full`` are forward-compatible
#: with fine-grained scopes (``tests:read``, etc.); ``offline_access``
#: triggers a refresh-token issuance per OAuth convention.
V1_SUPPORTED_SCOPES = frozenset({"read", "full", "offline_access"})

#: Public client identifier pattern (kept in lockstep with the SQL
#: CHECK constraint in the auth_client migration).
_CLIENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


class _AuthClientShared(BaseModel):
    """Common fields surfaced to the admin UI on read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    client_id: str
    name: Optional[str] = None
    expected_subject_azp: str
    expected_subject_audience: Optional[str] = None
    allowed_scopes: List[str]
    default_scope: str
    token_epoch: datetime
    disabled: bool
    created_at: datetime
    updated_at: datetime


class AuthClientResponse(_AuthClientShared):
    """Read-side response shape -- never carries the client_secret.

    Used by GET (list and detail), enable, and disable endpoints. The
    enforcement that this schema cannot leak the secret is structural:
    no ``client_secret`` field exists, and there is no inheritance
    path that adds one.
    """


class AuthClientCreatedResponse(_AuthClientShared):
    """One-shot response returned by create and rotate.

    The plaintext ``client_secret`` field is present **only** on this
    schema, in a response body, exactly once. The admin must copy it
    immediately; subsequent reads use :class:`AuthClientResponse`,
    which does not carry the field.
    """

    client_secret: str = Field(
        ...,
        description=(
            "Plaintext client secret. Returned exactly once on "
            "create / rotate; never retrievable again. Hand to the "
            "integration owner via a secure channel."
        ),
    )


class AuthClientCreate(BaseModel):
    """Request body for ``POST /orgs/{org_id}/auth-clients``."""

    client_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description=(
            "Public client identifier. Pattern ^[a-z0-9][a-z0-9_-]{2,63}$. "
            "Unique per-organization; two orgs may both have a 'brain' client."
        ),
    )
    name: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Human-readable label shown in the org settings UI.",
    )
    expected_subject_azp: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "Required azp claim of the subject token (RFC 8693). The "
            "subject token's azp must match this value exactly. This "
            "is the only mitigation against a co-tenant integration "
            "replaying its own valid Keycloak token at our endpoint."
        ),
    )
    expected_subject_audience: Optional[str] = Field(
        default=None,
        max_length=255,
        description=(
            "Optional aud claim the subject token must contain on "
            "top of the azp check; set when the configured IdP emits "
            "an aud."
        ),
    )
    allowed_scopes: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Set of scopes the client may request. v1 values: "
            "{'read','full','offline_access'}."
        ),
    )
    default_scope: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "Single scope token applied when the caller omits the "
            "scope parameter. Must be present in allowed_scopes."
        ),
    )

    @field_validator("client_id")
    @classmethod
    def _check_client_id_pattern(cls, v: str) -> str:
        if not _CLIENT_ID_RE.match(v):
            raise ValueError(
                "client_id must match ^[a-z0-9][a-z0-9_-]{2,63}$"
            )
        return v

    @field_validator("allowed_scopes")
    @classmethod
    def _check_allowed_scopes_supported(cls, v: List[str]) -> List[str]:
        # Deduplicate while preserving order so the round-trip through
        # the DB does not reorder a caller-meaningful default like
        # ``["read","offline_access"]``.
        seen: dict[str, None] = {}
        for s in v:
            if not s:
                raise ValueError("allowed_scopes entries must be non-empty")
            if s not in V1_SUPPORTED_SCOPES:
                raise ValueError(
                    f"allowed_scopes contains unsupported value {s!r}; "
                    f"v1 supports: {sorted(V1_SUPPORTED_SCOPES)}"
                )
            seen[s] = None
        return list(seen.keys())

    @field_validator("default_scope")
    @classmethod
    def _check_default_scope_is_single_token(cls, v: str) -> str:
        # ``default_scope`` is a single scope token, not a
        # space-separated list. Multi-scope defaults belong in
        # ``allowed_scopes`` + caller-passed ``scope`` parameter.
        if " " in v.strip():
            raise ValueError(
                "default_scope must be a single scope token "
                "(use allowed_scopes + the caller's scope param for multi)"
            )
        if v not in V1_SUPPORTED_SCOPES:
            raise ValueError(
                f"default_scope {v!r} not in v1 supported set "
                f"{sorted(V1_SUPPORTED_SCOPES)}"
            )
        return v

    @model_validator(mode="after")
    def _check_default_in_allowed(self) -> "AuthClientCreate":
        if self.default_scope not in self.allowed_scopes:
            raise ValueError(
                "default_scope must be one of allowed_scopes"
            )
        return self


__all__ = [
    "AuthClientCreate",
    "AuthClientCreatedResponse",
    "AuthClientResponse",
    "V1_SUPPORTED_SCOPES",
]

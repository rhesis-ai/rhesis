"""Schemas for the local-mode Rhesis platform API key endpoints.

These back the ``/platform/rhesis-key`` router. The raw key is only ever
accepted on input (``PlatformKeyUpdate``); it is never echoed back. Status
responses expose at most a masked suffix of the stored key.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PlatformKeyUpdate(BaseModel):
    """Request body for setting the org-scoped Rhesis platform API key."""

    key: str = Field(..., min_length=1, description="Rhesis platform API key (stored encrypted)")


class PlatformKeyStatus(BaseModel):
    """Status of the org-scoped Rhesis platform API key.

    Never contains the raw key -- only a masked suffix (``masked_key``) when a
    key is configured. ``valid`` and ``polyphemus_authorized`` are best-effort
    and may be ``None`` when they could not be determined.
    """

    configured: bool
    #: Where the effective key comes from. Only an ``organization`` key can be
    #: removed via DELETE; an ``environment`` key lives in the deployment's
    #: RHESIS_API_KEY and can only be overridden by storing an org key.
    source: Optional[Literal["organization", "environment"]] = None
    valid: Optional[bool] = None
    polyphemus_authorized: Optional[bool] = None
    masked_key: Optional[str] = None
    last_checked_at: Optional[str] = None

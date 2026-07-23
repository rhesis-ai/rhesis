"""Schemas for the local-only platform sync feature.

These are transient request/response DTOs (not persisted entities), so they use
plain ``BaseModel`` rather than the project ``Base`` schema, which would attach
``id``/``nano_id`` fields.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

DEFAULT_PLATFORM_BASE_URL = "https://api.rhesis.ai"


class PlatformSyncRequest(BaseModel):
    """Request body for ``POST /platform-sync``."""

    api_key: str = Field(..., min_length=1, description="A Rhesis platform API key (rh-...)")
    base_url: str = Field(
        default=DEFAULT_PLATFORM_BASE_URL,
        description="Platform base URL to pull from (defaults to production)",
    )
    resources: List[str] = Field(
        default_factory=list,
        description="Resource keys to sync (see GET /platform-sync/resources)",
    )


class SyncGap(BaseModel):
    """A field that could not be synced because the platform never returns it.

    Secrets (model provider keys, endpoint auth tokens/secrets) are write-only on
    the platform, so a synced record's secret field is left blank and reported here
    so the user knows to fill it in locally.
    """

    resource: str
    name: str
    field: str
    reason: str


class ResourceSyncResult(BaseModel):
    """Per-resource outcome of a sync run."""

    resource: str
    label: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    gaps: List[SyncGap] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class PlatformSyncSummary(BaseModel):
    """Aggregate result returned to the caller after a sync run."""

    base_url: str
    source_organization_id: Optional[str] = None
    source_user_email: Optional[str] = None
    results: List[ResourceSyncResult] = Field(default_factory=list)
    # Flattened across resources for a single "needs attention" list in the UI.
    gaps: List[SyncGap] = Field(default_factory=list)


class ResourceDescriptorOut(BaseModel):
    """A syncable resource advertised by ``GET /platform-sync/resources``."""

    key: str
    label: str
    dependencies: List[str] = Field(default_factory=list)
    description: Optional[str] = None

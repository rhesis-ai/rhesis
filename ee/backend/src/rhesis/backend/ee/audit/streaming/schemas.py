"""Request and response shapes of ``/audit-destinations``."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from rhesis.backend.ee.audit.streaming.adapters import DATADOG_SITES

Name = Annotated[str, Field(min_length=1, max_length=120)]
Secret = Annotated[str, Field(min_length=1, max_length=512)]
Url = Annotated[str, Field(min_length=1, max_length=2048)]


class WebhookCreate(BaseModel):
    """Signed with a secret Rhesis generates and returns once."""

    kind: Literal["webhook"]
    name: Name
    url: Url


class SplunkHecCreate(BaseModel):
    kind: Literal["splunk_hec"]
    name: Name
    url: Url = Field(description="The HEC event endpoint, ending in /services/collector/event")
    token: Secret


class DatadogCreate(BaseModel):
    kind: Literal["datadog"]
    name: Name
    site: Literal[DATADOG_SITES]  # type: ignore[valid-type]
    api_key: Secret


DestinationCreate = Annotated[
    Union[WebhookCreate, SplunkHecCreate, DatadogCreate],
    Field(discriminator="kind"),
]


class DestinationUpdate(BaseModel):
    paused: bool


class DestinationRead(BaseModel):
    id: UUID
    name: str
    kind: str
    # The config without its secrets.
    settings: dict
    paused: bool
    paused_reason: Optional[str] = None
    # Events recorded up to here have been delivered.
    delivered_through: datetime
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    consecutive_failures: int
    next_attempt_at: Optional[datetime] = None
    created_at: datetime


class DestinationCreated(DestinationRead):
    # Webhooks only, and only in this response.
    signing_secret: Optional[str] = None


class TestEventResult(BaseModel):
    delivered: bool
    error: Optional[str] = None

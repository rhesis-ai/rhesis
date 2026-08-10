import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .base import Base


class NotificationRead(Base):
    """A single notification, as returned by the API and carried in the
    websocket ``NOTIFICATION`` event payload."""

    event_type: str
    section: str
    title: str
    body: Optional[str] = None
    is_failure: bool
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    payload: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class NotificationSectionSummary(BaseModel):
    """Unread count and highlightable entity ids for one sidebar section."""

    unread: int = 0
    entity_ids: list[UUID] = Field(default_factory=list)


class NotificationSummaryResponse(BaseModel):
    """``GET /notifications/summary`` response, keyed by NotificationSection value."""

    sections: Dict[str, NotificationSectionSummary] = Field(default_factory=dict)


class NotificationMarkReadRequest(BaseModel):
    """``POST /notifications/read`` body.

    ``section`` marks every unread notification in that section read; ``ids``
    marks specific notifications read. At least one must be set (400 otherwise).
    The two narrow together, so passing both means "these ids, within this
    section".
    """

    section: Optional[str] = None
    ids: Optional[list[UUID]] = None

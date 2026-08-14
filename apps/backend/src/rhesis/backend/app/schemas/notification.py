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
    #: How many entities this one notification covers -- the badge adds this,
    #: not 1, so a Garak import of three test sets counts as three.
    item_count: int = 1
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

    ``section`` marks every unread notification in that section read;
    ``notification_ids`` marks specific notifications read. At least one must be
    set (400 otherwise). The two narrow together, so passing both means "these
    notifications, within this section".

    Named ``notification_ids`` rather than ``ids`` because notifications carry
    an ``entity_id`` and a ``payload["entity_ids"]`` too, and the whole
    highlight feature is built on entity ids -- passing those here would match
    nothing and silently report ``updated: 0``.
    """

    section: Optional[str] = None
    notification_ids: Optional[list[UUID]] = None

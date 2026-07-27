"""Pydantic schemas for Architect sessions and messages."""

from typing import Any, Dict, List, Optional

from pydantic import UUID4, ConfigDict

from .base import Base


class ArchitectMessageBase(Base):
    role: str
    content: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = None
    attachments: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class ArchitectMessageCreate(ArchitectMessageBase):
    session_id: Optional[UUID4] = None


class ArchitectMessage(ArchitectMessageBase):
    session_id: UUID4

    model_config = ConfigDict(from_attributes=True)


class ArchitectSessionBase(Base):
    title: Optional[str] = None
    mode: Optional[str] = "discovery"


class ArchitectSessionCreate(ArchitectSessionBase):
    """Create an Architect session.

    When ``initial_message`` is set, the backend persists it as the first user
    message and dispatches the Celery chat task in the same request so the
    session is already processing when the client opens it.
    """

    initial_message: Optional[str] = None


class ArchitectSessionUpdate(ArchitectSessionBase):
    plan_data: Optional[Dict[str, Any]] = None
    agent_state: Optional[Dict[str, Any]] = None


class ArchitectSession(ArchitectSessionBase):
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    project_id: Optional[UUID4] = None
    plan_data: Optional[Dict[str, Any]] = None
    agent_state: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ArchitectSessionDetail(ArchitectSession):
    messages: List[ArchitectMessage] = []

    model_config = ConfigDict(from_attributes=True)

"""Architect session and message models for the conversational test architect."""

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin


class ArchitectSession(Base, OrganizationMixin):
    """A conversation session with the Architect agent."""

    __tablename__ = "architect_session"

    user_id = Column(GUID(), ForeignKey("user.id"), nullable=False)
    title = Column(String(255), nullable=True)
    mode = Column(String(50), nullable=False, default="discovery")
    plan_data = Column(JSONB, nullable=True)
    agent_state = Column(JSONB, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    messages = relationship(
        "ArchitectMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ArchitectMessage.created_at",
    )
    organization = relationship("Organization")


class ArchitectMessage(Base):
    """A single message within an Architect session."""

    __tablename__ = "architect_message"

    session_id = Column(
        GUID(),
        ForeignKey("architect_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(20), nullable=False)  # user, assistant, system, event
    content = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    attachments = Column(JSONB, nullable=True)

    # Relationships
    session = relationship("ArchitectSession", back_populates="messages")

from sqlalchemy import Column, ForeignKey, Index, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.audit_policy import AuditLink, AuditPolicy
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.models.mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    OrganizationAndUserMixin,
    ProjectMixin,
    TagsMixin,
    TasksMixin,
)

requirement_source_association = Table(
    "requirement_source",
    Base.metadata,
    Column(
        "requirement_id",
        GUID(),
        ForeignKey("requirement.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("source_id", GUID(), ForeignKey("source.id", ondelete="CASCADE"), primary_key=True),
    # Where in the source the requirement comes from, e.g. "section 4.2".
    Column("note", Text, nullable=True),
    Column("user_id", GUID(), ForeignKey("user.id"), nullable=False),
    Column("organization_id", GUID(), ForeignKey("organization.id"), nullable=False),
    info={
        "audit": AuditLink(
            owner="requirement",
            owner_id="requirement_id",
            field="sources",
            linked_id="source_id",
        )
    },
)


class Requirement(
    Base,
    ActivityTrackableMixin,
    ProjectMixin,
    OrganizationAndUserMixin,
    TagsMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
):
    __tablename__ = "requirement"
    # review is the stored LLM quality review, rewritten wholesale on each run.
    __audit__ = AuditPolicy(plain=("description",), ignore=("review",))
    __table_args__ = (Index("ix_requirement_org_created", "organization_id", "created_at"),)
    name = Column(String, nullable=False)
    description = Column(Text)
    status_id = Column(GUID(), ForeignKey("status.id"))
    parent_id = Column(
        GUID(), ForeignKey("requirement.id", ondelete="SET NULL"), nullable=True, index=True
    )
    impact_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=True)
    review = Column(JSONB, nullable=True)

    status = relationship("Status", back_populates="requirements")
    prompts = relationship("Prompt", back_populates="requirement")
    tests = relationship("Test", back_populates="requirement")
    metrics = relationship("Metric", secondary="requirement_metric", back_populates="requirements")
    parent = relationship("Requirement", remote_side="Requirement.id", back_populates="children")
    # The FK's ON DELETE SET NULL unlinks children; don't load them to do it.
    children = relationship("Requirement", back_populates="parent", passive_deletes=True)
    impact = relationship("TypeLookup", foreign_keys=[impact_id])
    # viewonly: a link carries a note and tenant columns, so crud.requirement writes it.
    sources = relationship("Source", secondary=requirement_source_association, viewonly=True)

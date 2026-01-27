from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, relationship

from rhesis.backend.app.models.guid import GUID

from .base import Base
from .mixins import ActivityTrackableMixin, CommentsMixin, CountsMixin, TagsMixin, TasksMixin
from .test import test_test_set_association

# Association table for test_set and metric
test_set_metric_association = Table(
    "test_set_metric",
    Base.metadata,
    Column("test_set_id", GUID(), ForeignKey("test_set.id"), primary_key=True),
    Column("metric_id", GUID(), ForeignKey("metric.id"), primary_key=True),
    Column("user_id", GUID(), ForeignKey("user.id"), nullable=False),
    Column("organization_id", GUID(), ForeignKey("organization.id"), nullable=False),
)

"""
The TestSet model represents a collection of prompts that are used to test the performance 
of a model.

TODOs:
There are optimizations that can be made to speed the prompts being loaded into the test set.
Check this chat: https://chatgpt.com/share/671d684f-59a8-800f-8300-b2334a2e2ee5

In a nutshell, we can use a materialized view to store the prompts that are associated with 
the test set. This will allow us to speed up the process of loading the prompts into the test set.

The materialized view will be updated whenever the prompts are updated.

OR 

Create an index on the prompt_test_set table.

"""

prompt_test_set_association = Table(
    "prompt_test_set",
    Base.metadata,
    Column("prompt_id", GUID, ForeignKey("prompt.id")),
    Column("test_set_id", GUID, ForeignKey("test_set.id")),
    Column("user_id", GUID, ForeignKey("user.id")),
    Column("organization_id", GUID, ForeignKey("organization.id")),
)


class TestSet(Base, ActivityTrackableMixin, TagsMixin, CommentsMixin, TasksMixin, CountsMixin):
    __tablename__ = "test_set"
    name = Column(String, nullable=False)
    description = Column(Text)
    short_description = Column(Text)
    slug = Column(String)
    status_id = Column(GUID(), ForeignKey("status.id"))
    license_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    test_set_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    user_id = Column(GUID(), ForeignKey("user.id"))
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    attributes = Column(JSONB)
    is_published = Column(Boolean, default=False)
    visibility = Column(Text, default="organization")
    owner_id = Column(GUID(), ForeignKey("user.id"))
    assignee_id = Column(GUID(), ForeignKey("user.id"))
    priority = Column(Integer, default=0)

    __table_args__ = (
        CheckConstraint(
            "visibility IN ('public', 'organization', 'user')", name="test_set_visibility_check"
        ),
    )

    # Relationship to subscriptions
    status = relationship("Status", back_populates="test_sets")
    test_configurations = relationship("TestConfiguration", back_populates="test_set")
    license_type = relationship(
        "TypeLookup", back_populates="test_sets", foreign_keys=[license_type_id]
    )
    test_set_type = relationship(
        "TypeLookup", foreign_keys=[test_set_type_id], overlaps="test_set_types"
    )
    user = relationship("User", back_populates="test_sets", foreign_keys=[user_id])
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_test_sets")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_test_sets")
    organization = relationship("Organization", back_populates="test_sets")

    prompts = relationship(
        "Prompt", secondary=prompt_test_set_association, back_populates="test_sets"
    )

    tests = relationship(
        "Test", secondary=test_test_set_association, back_populates="test_sets", viewonly=True
    )

    # Metrics relationship - test set metrics override behavior metrics when present
    metrics = relationship(
        "Metric", secondary=test_set_metric_association, back_populates="test_sets"
    )

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(TestSet.id), Comment.entity_type == 'TestSet')",
        viewonly=True,
        uselist=True,
    )

    def _get_related_items(self, model_class, attribute_key):
        """Helper method to fetch related items from attributes"""
        session = Session.object_session(self)
        ids = self.attributes.get(attribute_key, []) if self.attributes else []
        return session.query(model_class).filter(model_class.id.in_(ids)).all()

    @hybrid_property
    def categories(self):
        from .category import Category

        return self._get_related_items(Category, "categories")

    @hybrid_property
    def topics(self):
        from .topic import Topic

        return self._get_related_items(Topic, "topics")

    @hybrid_property
    def behaviors(self):
        from .behavior import Behavior

        return self._get_related_items(Behavior, "behaviors")

    @hybrid_property
    def use_cases(self):
        from .use_case import UseCase

        return self._get_related_items(UseCase, "use_cases")

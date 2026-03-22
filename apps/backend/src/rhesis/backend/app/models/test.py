from sqlalchemy import Column, ForeignKey, Integer, Table, and_, case, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
    EmbeddableMixin,
    FilesMixin,
    OrganizationMixin,
    TagsMixin,
    TasksMixin,
)

# Association table for test_set and test
test_test_set_association = Table(
    "test_test_set",
    Base.metadata,
    Column("test_id", GUID(), ForeignKey("test.id"), primary_key=True),
    Column("test_set_id", GUID(), ForeignKey("test_set.id"), primary_key=True),
    Column("user_id", GUID(), ForeignKey("user.id")),
    Column("organization_id", GUID(), ForeignKey("organization.id")),
)


class Test(
    Base,
    EmbeddableMixin,
    ActivityTrackableMixin,
    TagsMixin,
    OrganizationMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
    FilesMixin,
):
    __tablename__ = "test"

    prompt_id = Column(GUID(), ForeignKey("prompt.id"))
    test_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    priority = Column(Integer)
    user_id = Column(GUID(), ForeignKey("user.id"))
    assignee_id = Column(GUID(), ForeignKey("user.id"))
    owner_id = Column(GUID(), ForeignKey("user.id"))
    # Configuration for test execution
    test_configuration = Column(JSONB)
    parent_id = Column(GUID(), ForeignKey("test.id"))
    topic_id = Column(GUID(), ForeignKey("topic.id"), index=True)
    behavior_id = Column(GUID(), ForeignKey("behavior.id"), index=True)
    category_id = Column(GUID(), ForeignKey("category.id"), index=True)
    status_id = Column(GUID(), ForeignKey("status.id"))
    source_id = Column(GUID(), ForeignKey("source.id"))
    # Test source info (origin, inputs, context)
    # Named 'test_metadata' to avoid SQLAlchemy's reserved 'metadata' attribute
    test_metadata = Column(JSONB)

    # Relationships
    prompt = relationship("Prompt", back_populates="tests")
    test_type = relationship("TypeLookup", back_populates="tests")
    user = relationship("User", foreign_keys=[user_id], back_populates="created_tests")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tests")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_tests")
    parent = relationship("Test", remote_side="[Test.id]", post_update=True)
    children = relationship("Test", foreign_keys=[parent_id], viewonly=True)
    topic = relationship("Topic", back_populates="tests")
    behavior = relationship("Behavior", back_populates="tests")
    category = relationship("Category", back_populates="tests")
    status = relationship("Status", back_populates="tests")
    source = relationship("Source", back_populates="tests")
    test_contexts = relationship("TestContext", back_populates="test")
    test_results = relationship("TestResult", back_populates="test")
    test_sets = relationship(
        "TestSet", secondary=test_test_set_association, back_populates="tests", viewonly=True
    )

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Test.id), Comment.entity_type == 'Test')",
        viewonly=True,
        uselist=True,
    )

    @hybrid_property
    def content(self):
        if self.test_configuration and self.test_configuration.get("goal"):
            return self.test_configuration["goal"]
        return self.prompt.content if self.prompt else None

    @content.expression
    def content(cls):
        from .prompt import Prompt

        # Mirror Python semantics: treat NULL and empty-string goal as absent
        goal_is_present = and_(
            cls.test_configuration["goal"].astext.isnot(None),
            cls.test_configuration["goal"].astext != "",
        )
        return case(
            (goal_is_present, cls.test_configuration["goal"].astext),
            else_=select(Prompt.content)
            .where(Prompt.id == cls.prompt_id)
            .correlate(cls)
            .scalar_subquery(),
        )

    def to_searchable_text(self) -> str:
        """
        Generate searchable text from test fields for embeddings and full-text search.

        Handles both test types:
        - Single-turn: Uses prompt.content and expected_response
        - Multi-turn: Uses test_configuration (goal, instructions, scenario, etc.)
        """
        from rhesis.backend.app.constants import TestType
        from rhesis.backend.tasks.execution.modes import get_test_type

        test_type = get_test_type(self)

        # Common metadata for both types
        metadata = [
            self.topic.name if self.topic else None,
            self.behavior.name if self.behavior else None,
            self.category.name if self.category else None,
        ]

        if test_type == TestType.MULTI_TURN:
            # Multi-turn: extract from test_configuration
            test_config = self.test_configuration or {}
            content = [
                test_config.get("goal"),
                test_config.get("instructions"),
                test_config.get("scenario"),
                test_config.get("restrictions"),
                test_config.get("context"),
            ]
        else:  # SINGLE_TURN (default)
            # Single-turn: extract from prompt
            content = [
                self.prompt.content if self.prompt else None,
                self.prompt.expected_response if self.prompt else None,
            ]

        return " ".join(filter(None, content + metadata))

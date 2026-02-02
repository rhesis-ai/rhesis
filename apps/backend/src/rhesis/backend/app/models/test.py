from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    ActivityTrackableMixin,
    CommentsMixin,
    CountsMixin,
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
    ActivityTrackableMixin,
    TagsMixin,
    OrganizationMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
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
    topic_id = Column(GUID(), ForeignKey("topic.id"))
    behavior_id = Column(GUID(), ForeignKey("behavior.id"))
    category_id = Column(GUID(), ForeignKey("category.id"))
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

    # Embedding relationship (polymorphic)
    embeddings = relationship(
        "Embedding",
        primaryjoin=(
            "and_(Embedding.entity_id == foreign(Test.id), Embedding.entity_type == 'Test')"
        ),
        foreign_keys="[Embedding.entity_id]",
        viewonly=True,
    )

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Test.id), Comment.entity_type == 'Test')",
        viewonly=True,
        uselist=True,
    )

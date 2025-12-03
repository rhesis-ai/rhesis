from sqlalchemy import (
    Column,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import (
    CommentsMixin,
    CountsMixin,
    OrganizationMixin,
    TagsMixin,
    TasksMixin,
)
from .test_set import prompt_test_set_association
from .use_case import prompt_use_case_association


class Prompt(
    Base,
    TagsMixin,
    OrganizationMixin,
    CommentsMixin,
    TasksMixin,
    CountsMixin,
):
    __tablename__ = "prompt"
    content = Column(Text, nullable=False)
    demographic_id = Column(
        GUID(), ForeignKey("demographic.id"), comment="The demographic for this prompt"
    )
    category_id = Column(GUID(), ForeignKey("category.id"))
    attack_category_id = Column(GUID(), ForeignKey("category.id"))
    topic_id = Column(GUID(), ForeignKey("topic.id"))
    language_code = Column(
        String,
        nullable=False,
        default="en-US",
        comment="Standardized language code with IETF language tag",
    )
    behavior_id = Column(GUID(), ForeignKey("behavior.id"))
    parent_id = Column(GUID(), ForeignKey("prompt.id"))
    prompt_template_id = Column(GUID(), ForeignKey("prompt_template.id"))
    expected_response = Column(Text)
    source_id = Column(GUID(), ForeignKey("source.id"))
    user_id = Column(GUID(), ForeignKey("user.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    user = relationship("User", back_populates="prompts")
    behavior = relationship("Behavior", back_populates="prompts")
    category = relationship(
        "Category", back_populates="prompts", foreign_keys="[Prompt.category_id]"
    )
    attack_category = relationship(
        "Category", back_populates="attack_prompts", foreign_keys="[Prompt.attack_category_id]"
    )
    topic = relationship("Topic", back_populates="prompts")
    status = relationship("Status", back_populates="prompts")
    source = relationship("Source", back_populates="prompts")
    demographic = relationship("Demographic", back_populates="prompts")
    prompt_template = relationship("PromptTemplate", back_populates="prompts")
    test_sets = relationship(
        "TestSet", secondary=prompt_test_set_association, back_populates="prompts"
    )
    use_cases = relationship(
        "UseCase", secondary=prompt_use_case_association, back_populates="prompts"
    )
    test_configurations = relationship("TestConfiguration", back_populates="prompt")
    parent = relationship("Prompt", back_populates="children", remote_side="[Prompt.id]")
    children = relationship("Prompt", back_populates="parent")
    tests = relationship("Test", back_populates="prompt")

    # Comments, tasks relationships and counts property are now provided by CommentTaskMixin

    def to_dict(self):
        """Convert the Prompt object to a dictionary with related names."""
        return {
            "nano_id": self.nano_id,
            "content": self.content,
            "demographic": self.demographic.name if self.demographic else None,
            "category": self.category.name if self.category else None,
            "attack_category": self.attack_category.name if self.attack_category else None,
            "topic": self.topic.name if self.topic else None,
            "language_code": self.language_code,
            "behavior": self.behavior.name if self.behavior else None,
            "parent": self.parent.content
            if self.parent
            else None,  # Assuming you want the content of the parent
            "prompt_template": self.prompt_template.content if self.prompt_template else None,
            "expected_response": self.expected_response,
            "source": self.source.title if self.source else None,
            "user": self.user.name if self.user else None,
            "status": self.status.name if self.status else None,
            # Add any other fields or related names you want to include
        }

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Category(Base, OrganizationAndUserMixin):
    __tablename__ = "category"
    name = Column(String)
    description = Column(Text)
    parent_id = Column(GUID(), ForeignKey("category.id"))
    entity_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    status = relationship("Status", back_populates="categories")
    parent = relationship("Category", back_populates="children", remote_side="[Category.id]")
    children = relationship("Category", back_populates="parent")
    prompt_templates = relationship("PromptTemplate", back_populates="category")
    prompts = relationship("Prompt", back_populates="category", foreign_keys="[Prompt.category_id]")
    attack_prompts = relationship(
        "Prompt", back_populates="attack_category", foreign_keys="[Prompt.attack_category_id]"
    )
    test_configurations = relationship("TestConfiguration", back_populates="category")
    entity_type = relationship("TypeLookup", back_populates="categories")
    tests = relationship("Test", back_populates="category")

    # Comment relationship (polymorphic)
    comments = relationship(
        "Comment",
        primaryjoin="and_(Comment.entity_id == foreign(Category.id), Comment.entity_type == 'Category')",
        viewonly=True,
        uselist=True,
    )

    @property
    def comment_count(self):
        """Get the count of comments for this category"""
        return len(self.comments) if self.comments else 0

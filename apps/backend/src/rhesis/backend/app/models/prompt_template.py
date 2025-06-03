from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin, TagsMixin


class PromptTemplate(Base, TagsMixin, OrganizationMixin):
    __tablename__ = "prompt_template"
    content = Column(Text, nullable=False)
    category_id = Column(GUID(), ForeignKey("category.id"))
    topic_id = Column(GUID(), ForeignKey("topic.id"))
    parent_id = Column(GUID(), ForeignKey("prompt_template.id"))
    language_code = Column(String)
    is_summary = Column(Boolean, default=False)
    source_id = Column(GUID(), ForeignKey("source.id"))
    user_id = Column(GUID(), ForeignKey("user.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    category = relationship("Category", back_populates="prompt_templates")
    topic = relationship("Topic", back_populates="prompt_templates")
    status = relationship("Status", back_populates="prompt_templates")
    source = relationship("Source", back_populates="prompt_templates")
    parent = relationship(
        "PromptTemplate", back_populates="children", remote_side="[PromptTemplate.id]"
    )
    children = relationship("PromptTemplate", back_populates="parent")
    user = relationship("User", back_populates="prompt_templates")
    prompts = relationship("Prompt", back_populates="prompt_template")

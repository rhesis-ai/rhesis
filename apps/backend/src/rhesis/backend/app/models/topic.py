from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Topic(Base, OrganizationAndUserMixin):
    __tablename__ = "topic"
    name = Column(String)
    description = Column(Text)
    parent_id = Column(GUID(), ForeignKey("topic.id"))
    entity_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    status = relationship("Status", back_populates="topics")
    parent = relationship("Topic", back_populates="children", remote_side="[Topic.id]")
    children = relationship("Topic", back_populates="parent")
    prompt_templates = relationship("PromptTemplate", back_populates="topic")
    prompts = relationship("Prompt", back_populates="topic")
    test_configurations = relationship("TestConfiguration", back_populates="topic")
    entity_type = relationship("TypeLookup", back_populates="topics")
    tests = relationship("Test", back_populates="topic")

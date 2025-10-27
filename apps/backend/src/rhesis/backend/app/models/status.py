from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Status(Base, OrganizationAndUserMixin):
    __tablename__ = "status"
    name = Column(String)
    description = Column(Text)
    entity_type_id = Column(GUID(), ForeignKey("type_lookup.id"))

    entity_type = relationship("TypeLookup", back_populates="statuses")

    behaviors = relationship("Behavior", back_populates="status")
    categories = relationship("Category", back_populates="status")
    endpoints = relationship("Endpoint", back_populates="status")
    topics = relationship("Topic", back_populates="status")
    prompt_templates = relationship("PromptTemplate", back_populates="status")
    prompts = relationship("Prompt", back_populates="status")
    test_sets = relationship("TestSet", back_populates="status")
    risks = relationship("Risk", back_populates="status")
    subscriptions = relationship("Subscription", back_populates="status")
    test_configurations = relationship("TestConfiguration", back_populates="status")
    test_runs = relationship("TestRun", back_populates="status")
    test_results = relationship("TestResult", back_populates="status")
    use_cases = relationship("UseCase", back_populates="status")
    tests = relationship("Test", back_populates="status")
    projects = relationship("Project", back_populates="status")
    metrics = relationship("Metric", back_populates="status")
    models = relationship("Model", back_populates="status")
    tasks = relationship("Task", back_populates="status")
    sources = relationship("Source", back_populates="status")

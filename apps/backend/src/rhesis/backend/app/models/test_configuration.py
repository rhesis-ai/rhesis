from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin


class TestConfiguration(Base, OrganizationMixin):
    __tablename__ = "test_configuration"
    endpoint_id = Column(GUID(), ForeignKey("endpoint.id"), nullable=False)
    category_id = Column(GUID(), ForeignKey("category.id"))
    topic_id = Column(GUID(), ForeignKey("topic.id"))
    prompt_id = Column(GUID(), ForeignKey("prompt.id"))
    use_case_id = Column(GUID(), ForeignKey("use_case.id"))
    test_set_id = Column(GUID(), ForeignKey("test_set.id"))
    user_id = Column(GUID(), ForeignKey("user.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    attributes = Column(JSONB, nullable=True)

    category = relationship("Category", back_populates="test_configurations")
    topic = relationship("Topic", back_populates="test_configurations")
    prompt = relationship("Prompt", back_populates="test_configurations")
    use_case = relationship("UseCase", back_populates="test_configurations")
    test_set = relationship("TestSet", back_populates="test_configurations")
    user = relationship("User", back_populates="test_configurations")
    status = relationship("Status", back_populates="test_configurations")
    test_results = relationship("TestResult", back_populates="test_configuration")
    test_runs = relationship("TestRun", back_populates="test_configuration")
    endpoint = relationship("Endpoint", back_populates="test_configurations")

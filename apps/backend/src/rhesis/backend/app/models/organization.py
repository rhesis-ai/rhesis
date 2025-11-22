from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import TagsMixin


class Organization(Base, TagsMixin):
    __tablename__ = "organization"

    # Basic information
    name = Column(String, nullable=False)
    display_name = Column(String)  # A friendly name for display purposes
    description = Column(Text)
    website = Column(String)
    logo_url = Column(String)

    # Contact information
    email = Column(String)
    phone = Column(String)
    address = Column(Text)

    # Organization settings
    is_active = Column(Boolean, default=True)
    max_users = Column(Integer)  # Limit on number of users
    subscription_ends_at = Column(DateTime)  # When org subscription expires

    # Domain verification
    domain = Column(String)  # For automatic user association
    is_domain_verified = Column(Boolean, default=False)
    is_onboarding_complete = Column(Boolean, default=False)

    # Relationships with explicit UUID columns
    owner_id = Column(GUID(), ForeignKey("user.id"))
    user_id = Column(GUID(), ForeignKey("user.id"))

    # Relationships
    users = relationship(
        "User", back_populates="organization", foreign_keys="[User.organization_id]"
    )
    test_sets = relationship("TestSet", back_populates="organization")
    endpoints = relationship("Endpoint", back_populates="organization")
    projects = relationship("Project", back_populates="organization")
    behaviors = relationship("Behavior", back_populates="organization")
    categories = relationship("Category", back_populates="organization")
    demographics = relationship("Demographic", back_populates="organization")
    dimensions = relationship("Dimension", back_populates="organization")
    statuses = relationship("Status", back_populates="organization")
    test_configurations = relationship("TestConfiguration", back_populates="organization")
    test_results = relationship("TestResult", back_populates="organization")
    test_runs = relationship("TestRun", back_populates="organization")
    tests = relationship("Test", back_populates="organization")
    tokens = relationship("Token", back_populates="organization")
    type_lookups = relationship("TypeLookup", back_populates="organization")
    use_cases = relationship("UseCase", back_populates="organization")
    tools = relationship("Tool", back_populates="organization")

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

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
    subscription_ends_at = Column(DateTime(timezone=True))  # When org subscription expires

    # Domain verification
    domain = Column(String)  # For automatic user association
    is_domain_verified = Column(Boolean, default=False)
    is_onboarding_complete = Column(Boolean, default=False)

    # Per-organization JSON configuration parsed by EE-aware consumers
    # (e.g. SSO). The schema is owned by the consumer; core stores it
    # as opaque JSON and never inspects its keys.
    sso_config = Column(JSON, nullable=True)

    # Opaque signed license token consumed by the EE licensing layer.
    # Core never inspects its contents; the EE SignedTokenLicenseProvider
    # decodes and validates it. Modeled on sso_config.
    license = Column(Text, nullable=True)

    slug = Column(String(50), unique=True, index=True, nullable=True)

    # Org-scoped Rhesis platform API key for local/self-hosted deployments.
    # Encrypted at rest (same EncryptedString type as Model.key). When set it
    # overrides the process-wide RHESIS_API_KEY env var for this organization.
    rhesis_api_key = Column(EncryptedString(), nullable=True)
    # Cached result of the last platform-key validation against the hosted
    # platform, so status reads and model-availability annotation never need to
    # re-probe over the network on the GET /models hot path. Nullable tri-state:
    # None means "unknown / not yet validated".
    rhesis_key_valid = Column(Boolean, nullable=True)
    rhesis_key_polyphemus_authorized = Column(Boolean, nullable=True)
    # Caches when the stored platform key was last validated against the
    # hosted platform, so status reads need not re-probe on every call.
    rhesis_key_last_checked_at = Column(DateTime(timezone=True), nullable=True)

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
    requirements = relationship("Requirement", back_populates="organization")
    categories = relationship("Category", back_populates="organization")
    statuses = relationship("Status", back_populates="organization")
    test_configurations = relationship("TestConfiguration", back_populates="organization")
    test_results = relationship("TestResult", back_populates="organization")
    test_runs = relationship("TestRun", back_populates="organization")
    tests = relationship("Test", back_populates="organization")
    tokens = relationship("Token", back_populates="organization")
    type_lookups = relationship("TypeLookup", back_populates="organization")
    tools = relationship("Tool", back_populates="organization")

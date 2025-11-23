from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

from .base import Base
from .enums import (
    EndpointConfigSource,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from .guid import GUID
from .mixins import TagsMixin


class Endpoint(Base, TagsMixin):
    __tablename__ = "endpoint"
    # Core Fields
    name = Column(String, nullable=False)
    description = Column(String)
    connection_type = Column(String, nullable=False)
    url = Column(String, nullable=True)
    auth = Column(JSON)
    environment = Column(String, nullable=False, default=EndpointEnvironment.DEVELOPMENT.value)

    # Configuration Source
    config_source = Column(String, nullable=False, default=EndpointConfigSource.MANUAL.value)
    openapi_spec_url = Column(String)
    openapi_spec = Column(JSON)
    llm_suggestions = Column(JSON)
    endpoint_metadata = Column(JSON)

    # Request Structure
    method = Column(String)  # Required for REST
    endpoint_path = Column(String)
    request_headers = Column(JSON)
    query_params = Column(JSON)
    request_mapping = Column(JSON)
    input_mappings = Column(JSON)

    # Response Handling
    response_format = Column(String, nullable=False, default=EndpointResponseFormat.JSON.value)
    response_mapping = Column(JSON)
    validation_rules = Column(JSON)

    # Status relationship (keeping existing relationship)
    status_id = Column(GUID(), ForeignKey("status.id"))
    status = relationship("Status", back_populates="endpoints")

    # User relationship
    user_id = Column(GUID(), ForeignKey("user.id"))
    user = relationship("User", back_populates="endpoints")

    # Organization relationship
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    organization = relationship("Organization", back_populates="endpoints")

    # Project relationship
    project_id = Column(GUID(), ForeignKey("project.id"), nullable=True)
    project = relationship("Project", back_populates="endpoints")

    # Test Configuration relationship
    test_configurations = relationship("TestConfiguration", back_populates="endpoint")

    # Authentication fields
    auth_type = Column(String, nullable=True)
    auth_token = Column(EncryptedString(), nullable=True)  # Encrypted for security
    client_id = Column(Text, nullable=True)
    client_secret = Column(EncryptedString(), nullable=True)  # Encrypted for security
    token_url = Column(Text, nullable=True)
    scopes = Column(ARRAY(Text), nullable=True)
    audience = Column(Text, nullable=True)
    extra_payload = Column(JSON, nullable=True)
    last_token = Column(EncryptedString(), nullable=True)  # Encrypted for security
    last_token_expires_at = Column(DateTime, nullable=True)

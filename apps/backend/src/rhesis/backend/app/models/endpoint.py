from sqlalchemy import Column, ForeignKey, String, Text, Enum
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy.orm import relationship

from .base import Base
from .enums import EndpointConfigSource, EndpointEnvironment, EndpointResponseFormat, EndpointAuthType
from .guid import GUID
from .mixins import TagsMixin


class Endpoint(Base, TagsMixin):
    __tablename__ = "endpoint"
    # Core Fields
    name = Column(String, nullable=False)
    description = Column(String)
    protocol = Column(String, nullable=False)
    url = Column(String, nullable=False)
    auth = Column(JSON)
    environment = Column(String, nullable=False, default=EndpointEnvironment.DEVELOPMENT.value)

    # Configuration Source
    config_source = Column(String, nullable=False, default=EndpointConfigSource.MANUAL.value)
    openapi_spec_url = Column(String)
    openapi_spec = Column(JSON)
    llm_suggestions = Column(JSON)

    # Request Structure
    method = Column(String)  # Required for REST
    endpoint_path = Column(String)
    request_headers = Column(JSON)
    query_params = Column(JSON)
    request_body_template = Column(JSON)
    input_mappings = Column(JSON)

    # Response Handling
    response_format = Column(String, nullable=False, default=EndpointResponseFormat.JSON.value)
    response_mappings = Column(JSON)
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
    auth_token = Column(Text, nullable=True)
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)
    token_url = Column(Text, nullable=True)
    scopes = Column(ARRAY(Text), nullable=True)
    audience = Column(Text, nullable=True)
    extra_payload = Column(JSON, nullable=True)

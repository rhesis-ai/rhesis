from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin


class Tool(Base, OrganizationMixin):
    __tablename__ = "tool"

    # Basic information
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Tool configuration
    tool_type_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=True)
    tool_provider_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=True)
    status_id = Column(GUID(), ForeignKey("status.id"), nullable=True)

    # Authentication (encrypted)
    auth_token = Column(EncryptedString(), nullable=False)

    # Provider-specific configuration (JSON with {{auth_token}} placeholders)
    tool_metadata = Column(JSONB, nullable=False, default=dict)

    # Relationships
    tool_type = relationship("TypeLookup", foreign_keys=[tool_type_id], back_populates="tool_types")
    tool_provider = relationship(
        "TypeLookup", foreign_keys=[tool_provider_id], back_populates="tool_providers"
    )
    status = relationship("Status", foreign_keys=[status_id], back_populates="tools")

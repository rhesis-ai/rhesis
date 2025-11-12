from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint
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
    tool_type_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=False)
    tool_provider_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=False)
    status_id = Column(GUID(), ForeignKey("status.id"), nullable=False)

    # Authentication (encrypted)
    auth_token = Column(EncryptedString(), nullable=False)

    # Provider-specific configuration (JSON with {{auth_token}} placeholders)
    tool_metadata = Column(JSONB, nullable=False, default=dict)

    # Relationships
    tool_type = relationship("TypeLookup", foreign_keys=[tool_type_id])
    tool_provider = relationship("TypeLookup", foreign_keys=[tool_provider_id])
    status = relationship("Status", foreign_keys=[status_id])

    # Constraints
    __table_args__ = (
        UniqueConstraint("organization_id", "tool_provider_id", name="uq_org_tool_provider"),
    )

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Tool(Base, OrganizationAndUserMixin):
    __tablename__ = "tool"

    # Basic information
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Tool configuration
    tool_type_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=False)
    tool_provider_type_id = Column(GUID(), ForeignKey("type_lookup.id"), nullable=False)
    status_id = Column(GUID(), ForeignKey("status.id"), nullable=True)

    # Authentication credentials (encrypted JSON containing all auth data)
    # Examples: {"NOTION_TOKEN": "ntn_abc..."} or
    credentials = Column(EncryptedString(), nullable=False)

    tool_metadata = Column(JSONB, nullable=True, default=None)

    # Relationships
    tool_type = relationship("TypeLookup", foreign_keys=[tool_type_id], back_populates="tool_types")
    tool_provider_type = relationship(
        "TypeLookup", foreign_keys=[tool_provider_type_id], back_populates="tool_provider_types"
    )
    status = relationship("Status", foreign_keys=[status_id], back_populates="tools")
    user = relationship("User", foreign_keys="[Tool.user_id]", back_populates="tools")
    organization = relationship(
        "Organization", foreign_keys="[Tool.organization_id]", back_populates="tools"
    )

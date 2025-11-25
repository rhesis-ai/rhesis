from sqlalchemy import JSON, Boolean, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

from .base import Base
from .guid import GUID
from .mixins import CommentsMixin, CountsMixin, OrganizationAndUserMixin, TagsMixin, TasksMixin


class Model(Base, OrganizationAndUserMixin, TagsMixin, CommentsMixin, TasksMixin, CountsMixin):
    __tablename__ = "model"

    # Basic information
    name = Column(String, nullable=False)
    description = Column(Text)
    icon = Column(String)
    model_name = Column(String, nullable=False)
    endpoint = Column(String, nullable=True)  # Optional for cloud providers (OpenAI, Gemini, etc.)
    key = Column(
        EncryptedString(), nullable=False
    )  # Encrypted for security (LLM provider API keys)
    request_headers = Column(JSON)
    is_protected = Column(Boolean, default=False, nullable=False)  # System models cannot be deleted

    # Provider type relationship
    provider_type_id = Column(GUID(), ForeignKey("type_lookup.id"))
    provider_type = relationship(
        "TypeLookup", foreign_keys=[provider_type_id], back_populates="models"
    )

    # Status relationship
    status_id = Column(GUID(), ForeignKey("status.id"))
    status = relationship("Status", foreign_keys=[status_id], back_populates="models")

    # Owner relationship (using UserOwnedMixin for user_id)
    owner_id = Column(GUID(), ForeignKey("user.id"))
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_models")

    # Assignee relationship
    assignee_id = Column(GUID(), ForeignKey("user.id"))
    assignee = relationship(
        "User", foreign_keys=[assignee_id], back_populates="assigned_models", overlaps="owner"
    )

    # Metrics relationship
    metrics = relationship("Metric", back_populates="model")

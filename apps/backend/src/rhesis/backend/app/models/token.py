from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import OrganizationMixin
from rhesis.backend.app.utils.encryption import EncryptedString


class Token(Base, OrganizationMixin):
    __tablename__ = "token"

    name = Column(String)

    # Token-specific columns
    token = Column(EncryptedString(), nullable=False)  # Encrypted for security (user-generated tokens)
    token_obfuscated = Column(String)
    token_type = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime)
    last_refreshed_at = Column(DateTime)
    user_id = Column(ForeignKey("user.id"), nullable=False)

    # Relationship to user
    user = relationship("User", back_populates="tokens")

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired"""
        if not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires_at = (
            self.expires_at
            if self.expires_at.tzinfo
            else self.expires_at.replace(tzinfo=timezone.utc)
        )
        return expires_at <= now

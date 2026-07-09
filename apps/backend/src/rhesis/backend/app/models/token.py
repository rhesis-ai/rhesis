from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.utils.encryption import EncryptedString

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin


class Token(Base, OrganizationMixin):
    __tablename__ = "token"

    name = Column(String)

    # Token-specific columns
    token = Column(
        EncryptedString(), nullable=False
    )  # Encrypted for security (user-generated tokens)
    token_hash = Column(
        String(64), index=True, unique=True, nullable=False
    )  # SHA-256 hash for lookups
    token_obfuscated = Column(String)
    token_type = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True))
    last_refreshed_at = Column(DateTime(timezone=True))
    user_id = Column(ForeignKey("user.id"), nullable=False)

    # Optional project scope - no FK so token lookups work before tenant context is resolved.
    # When set, the token is restricted to that project's scope.
    project_id = Column(GUID(), nullable=True, index=True)

    # SP9: optional explicit permission subset (JSON array of capability strings).
    # NULL means the token inherits the owner's full access. When set, the EE
    # provider intersects these scopes with the owner's effective permissions —
    # a token can never exceed its issuer's access at check time (auto-narrows
    # on owner downgrade without needing a DB update).
    scopes = Column(JSONB, nullable=True)

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

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID


class RefreshToken(Base):
    """Refresh token for short-lived access token rotation.

    Stores hashed refresh tokens. The raw token is returned to the
    client once on creation; only the SHA-256 hash is persisted.

    ``family_id`` groups tokens created via rotation.  If a revoked
    token from the same family is presented, the entire family is
    revoked (reuse detection).

    Token-exchange-issued tokens additionally carry ``client_id`` and
    ``scope``. When ``client_id IS NOT NULL``, ``POST /auth/refresh``
    requires HTTP Basic client credentials matching the AuthClient row
    (defense in depth: a refresh-token thief without the client secret
    cannot rotate). ``scope`` is preserved across rotation so a
    ``scope=read`` token never silently escalates to full-user access
    on its first refresh. UI/SSO refresh tokens leave both columns
    NULL and behave exactly as before this column was added.
    """

    __tablename__ = "refresh_token"

    user_id = Column(
        GUID(),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex digest of the raw opaque token",
    )
    family_id = Column(
        GUID(),
        nullable=False,
        index=True,
        comment="Groups tokens in a rotation chain for reuse detection",
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when the token is explicitly revoked",
    )
    client_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment=(
            "AuthClient.client_id when this row was minted via "
            "/auth/token-exchange. NULL for UI/SSO refresh tokens."
        ),
    )
    scope = Column(
        String(255),
        nullable=True,
        comment=(
            "Space-separated scope string preserved across rotation; set when client_id is set."
        ),
    )

    # Relationships
    user = relationship("User", backref="refresh_tokens")

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires_at = (
            self.expires_at
            if self.expires_at.tzinfo
            else self.expires_at.replace(tzinfo=timezone.utc)
        )
        return expires_at <= now

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_revoked

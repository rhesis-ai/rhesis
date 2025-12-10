from nanoid import generate
from sqlalchemy import (
    TIMESTAMP,
    Column,
    DateTime,
    String,
    func,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import as_declarative, declared_attr

from rhesis.backend.app.models.guid import GUID

# Define a custom alphabet without underscores
custom_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@as_declarative()
class Base:
    id = Column(
        GUID(), primary_key=True, index=True, unique=True, server_default=text("gen_random_uuid()")
    )
    nano_id = Column(
        String, unique=True, default=lambda: generate(size=12, alphabet=custom_alphabet)
    )
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Soft delete support
    deleted_at = Column(DateTime, nullable=True, index=True)

    @hybrid_property
    def is_deleted(self):
        """Check if this record is soft-deleted"""
        return self.deleted_at is not None

    @is_deleted.expression
    def is_deleted(cls):
        """SQL expression for is_deleted filter"""
        return cls.deleted_at.isnot(None)

    def soft_delete(self):
        """Mark this record as deleted"""
        from datetime import datetime, timezone

        self.deleted_at = datetime.now(timezone.utc)

    def restore(self):
        """Restore a soft-deleted record"""
        self.deleted_at = None

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

from sqlalchemy import Column, Integer, LargeBinary, String, Text
from sqlalchemy.orm import deferred

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class File(Base, OrganizationAndUserMixin):
    __tablename__ = "file"

    # File content (deferred - never loaded on queries unless explicitly requested)
    content = deferred(Column(LargeBinary))

    # File metadata
    filename = Column(String(255), nullable=False)
    content_type = Column(String(127), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    # Polymorphic entity reference
    entity_id = Column(GUID(), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)

    # Ordering for multiple files on same entity
    position = Column(Integer, nullable=False, default=0)

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin
from .use_case import risk_use_case_association


class Risk(Base, OrganizationAndUserMixin):
    __tablename__ = "risk"
    name = Column(String)
    description = Column(Text)
    parent_id = Column(GUID(), ForeignKey("risk.id"))
    status_id = Column(GUID(), ForeignKey("status.id"))
    # Relationship to status
    status = relationship("Status", back_populates="risks")
    # Relationship to parent
    parent = relationship("Risk", back_populates="children", remote_side="[Risk.id]")
    # Relationship to children
    children = relationship("Risk", back_populates="parent")

    # Relationship to use cases
    use_cases = relationship("UseCase", secondary=risk_use_case_association, back_populates="risks")

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Demographic(Base, OrganizationAndUserMixin):
    __tablename__ = "demographic"
    name = Column(String, nullable=False)
    description = Column(Text)
    dimension_id = Column(GUID(), ForeignKey("dimension.id"))
    dimension = relationship("Dimension", back_populates="demographics")
    prompts = relationship("Prompt", back_populates="demographic")

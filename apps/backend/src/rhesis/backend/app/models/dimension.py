from sqlalchemy import (
    Column,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import OrganizationAndUserMixin, ProjectMixin


class Dimension(Base, ProjectMixin, OrganizationAndUserMixin):
    __tablename__ = "dimension"
    name = Column(String, nullable=False)
    description = Column(Text)
    demographics = relationship("Demographic", back_populates="dimension")

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.guid import GUID

from .base import Base
from .mixins import OrganizationAndUserMixin

risk_use_case_association = Table(
    "risk_use_case",
    Base.metadata,
    Column("risk_id", GUID, ForeignKey("risk.id")),
    Column("use_case_id", GUID, ForeignKey("use_case.id")),
    Column("user_id", GUID, ForeignKey("user.id")),
    Column("organization_id", GUID, ForeignKey("organization.id")),
)

prompt_use_case_association = Table(
    "prompt_use_case",
    Base.metadata,
    Column("prompt_id", GUID, ForeignKey("prompt.id")),
    Column("use_case_id", GUID, ForeignKey("use_case.id")),
    Column("user_id", GUID, ForeignKey("user.id")),
    Column("organization_id", GUID, ForeignKey("organization.id")),
)


class UseCase(Base, OrganizationAndUserMixin):
    __tablename__ = "use_case"
    name = Column(String, nullable=False)
    description = Column(Text)
    industry = Column(String)
    application = Column(String)
    is_active = Column(Boolean, default=True)
    status_id = Column(GUID(), ForeignKey("status.id"))

    # Relationship to subscriptions
    status = relationship("Status", back_populates="use_cases")

    risks = relationship("Risk", secondary=risk_use_case_association, back_populates="use_cases")
    prompts = relationship(
        "Prompt", secondary=prompt_use_case_association, back_populates="use_cases"
    )
    test_configurations = relationship("TestConfiguration", back_populates="use_case")
    # test_sets = relationship("TestSet", back_populates="use_case")

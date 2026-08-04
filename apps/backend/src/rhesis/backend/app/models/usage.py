from sqlalchemy import BigInteger, Column, Date, ForeignKey, Index, String, UniqueConstraint, text

from .base import Base
from .guid import GUID


class Usage(Base):
    """Cumulative usage counter for a metered resource within a billing period.

    Not org-scoped via ``OrganizationMixin``: the usage service performs
    explicit atomic upserts (``INSERT ... ON CONFLICT DO UPDATE``), which
    the ambient tenant auto-filter/auto-stamp listeners are not built for.
    Protected by a ``tenant_isolation`` RLS policy at the database level
    instead (see the ``77df3dbea77d_add_usage_table`` migration).

    Excluded from the generic recycle-bin routes (see
    ``routers/recycle.py``) -- see that module for why.

    ``resource`` stores :class:`~rhesis.backend.app.quota.QuotaResource`
    string values. Application code always writes through the enum, never
    a raw string.
    """

    __tablename__ = "usage"

    organization_id = Column(
        GUID(), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    resource = Column(String(64), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    used = Column(BigInteger, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "resource",
            "period_start",
            name="uq_usage_org_resource_period",
        ),
        Index("ix_usage_organization_id", "organization_id"),
    )

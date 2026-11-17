from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from rhesis.backend.app.models.audit_policy import NOT_AUDITED, AuditLink, AuditPolicy
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.guid import GUID
from rhesis.backend.app.models.mixins import (
    ActivityTrackableMixin,
    OrganizationAndUserMixin,
    ProjectMixin,
)

REPORT_STATUS_DRAFT = "draft"
REPORT_STATUS_PUBLISHED = "published"
REPORT_RECOMMENDATIONS = ("ready", "ready_with_risks", "not_ready")
# How a test that ran in several picked runs is counted.
RESULT_RULE_LATEST = "latest"
RESULT_RULE_ALL = "all"
RESULT_RULE_WORST = "worst"


def _link_table(name: str, column: str, target: str, field: str) -> Table:
    return Table(
        name,
        Base.metadata,
        Column("report_id", GUID(), ForeignKey("report.id", ondelete="CASCADE"), primary_key=True),
        # Indexed as in the migration: ix_<table>_<column>, ix_<table>_organization_id.
        Column(
            column,
            GUID(),
            ForeignKey(f"{target}.id", ondelete="CASCADE"),
            primary_key=True,
            index=True,
        ),
        Column("user_id", GUID(), ForeignKey("user.id"), nullable=False),
        Column(
            "organization_id", GUID(), ForeignKey("organization.id"), nullable=False, index=True
        ),
        info={
            "audit": AuditLink(owner="report", owner_id="report_id", field=field, linked_id=column)
        },
    )


report_test_run_association = _link_table("report_test_run", "test_run_id", "test_run", "test_runs")
report_requirement_association = _link_table(
    "report_requirement", "requirement_id", "requirement", "requirements"
)


class Report(Base, ActivityTrackableMixin, ProjectMixin, OrganizationAndUserMixin):
    """A summary of one endpoint's test runs, live while draft and frozen once published."""

    __tablename__ = "report"
    # The snapshots are large and derived; publishing is recorded as report.published.
    __audit__ = AuditPolicy(
        plain=("summary", "snapshot_hash"), ignore=("endpoint_snapshot", "metrics", "sections")
    )
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_report_status"),
        CheckConstraint("result_rule IN ('latest','all','worst')", name="ck_report_result_rule"),
        CheckConstraint(
            "recommendation IS NULL OR recommendation IN ('ready','ready_with_risks','not_ready')",
            name="ck_report_recommendation",
        ),
    )

    title = Column(String, nullable=False)
    endpoint_id = Column(GUID(), ForeignKey("endpoint.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default=REPORT_STATUS_DRAFT, server_default="draft")
    result_rule = Column(
        String, nullable=False, default=RESULT_RULE_LATEST, server_default=RESULT_RULE_LATEST
    )
    # Off for a plain report across runs (e.g. experiments): no ship recommendation.
    is_release = Column(Boolean, nullable=False, default=True, server_default="true")
    # While a draft, runs on the endpoint with this tag join the picked ones;
    # publish freezes the resolved list into report_test_run.
    run_tag = Column(String, nullable=True)
    # The published report this one is compared with; none means no comparison.
    baseline_report_id = Column(GUID(), ForeignKey("report.id", ondelete="SET NULL"), nullable=True)
    summary = Column(Text, nullable=True)
    recommendation = Column(String, nullable=True)
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    published_by_id = Column(GUID(), ForeignKey("user.id"), nullable=True)
    endpoint_snapshot = Column(JSONB, nullable=True)
    metrics = Column(JSONB, nullable=True)
    # Output of the registered report sections (EE), keyed by section, frozen at publish.
    sections = Column(JSONB, nullable=True)
    snapshot_hash = Column(String, nullable=True)

    endpoint = relationship("Endpoint")
    published_by = relationship("User", foreign_keys=[published_by_id])
    test_runs = relationship("TestRun", secondary=report_test_run_association, viewonly=True)
    requirements = relationship(
        "Requirement", secondary=report_requirement_association, viewonly=True
    )
    results = relationship(
        "ReportResult", back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def is_published(self) -> bool:
        return self.status == REPORT_STATUS_PUBLISHED

    @property
    def endpoint_ref(self):
        """The endpoint as the report shows it: frozen once published, live while a draft."""
        if self.is_published and self.endpoint_snapshot:
            return {"id": self.endpoint_id, "name": self.endpoint_snapshot.get("name")}
        return self.endpoint


class ReportResult(Base, ProjectMixin):
    """One counted test result, frozen when its report is published."""

    __tablename__ = "report_result"
    __audit__ = NOT_AUDITED  # written once per publish, covered by report.published

    report_id = Column(
        GUID(), ForeignKey("report.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(GUID(), ForeignKey("organization.id"), nullable=False, index=True)
    # No FKs below: a frozen row must outlive the test, run or requirement it records.
    test_id = Column(GUID(), nullable=False)
    test_result_id = Column(GUID(), nullable=False)
    test_run_id = Column(GUID(), nullable=False)
    requirement_id = Column(GUID(), nullable=True)
    parent_requirement_id = Column(GUID(), nullable=True)
    execution = Column(String, nullable=False)
    verdict = Column(String, nullable=True)
    overridden = Column(Boolean, nullable=False, default=False, server_default="false")

    report = relationship("Report", back_populates="results")

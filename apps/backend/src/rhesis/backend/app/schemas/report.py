from datetime import datetime
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.base import Base, BulkIds, ServerIdentity
from rhesis.backend.app.schemas.user import UserReference

ReportRecommendation = Literal["ready", "ready_with_risks", "not_ready"]
ReportStatus = Literal["draft", "published"]

# Actions a published report no longer offers, whatever the caller's role.
_CLOSED_WHEN_PUBLISHED = ("report:update", "report:delete", "report:publish")


class ReportBase(Base):
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = None
    recommendation: Optional[ReportRecommendation] = None


class ReportCreate(ReportBase):
    endpoint_id: UUID4
    test_run_ids: BulkIds = Field(default_factory=list)
    requirement_ids: BulkIds = Field(default_factory=list)


class ReportUpdate(Base):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = None
    recommendation: Optional[ReportRecommendation] = None
    test_run_ids: Optional[BulkIds] = None
    requirement_ids: Optional[BulkIds] = None


class ReportEndpointRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str


class Report(ReportBase, WithPermittedActions, ServerIdentity):
    __resource_type__: ClassVar[Optional[str]] = ResourceType.REPORT

    endpoint_id: UUID4
    status: ReportStatus
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    published_by_id: Optional[UUID4] = None
    snapshot_hash: Optional[str] = None
    user: Optional[UserReference] = None
    published_by: Optional[UserReference] = None
    endpoint: Optional[ReportEndpointRef] = None

    @model_validator(mode="after")
    def _close_published(self) -> "Report":
        if self.status == "published":
            self.permitted_actions = [
                a for a in self.permitted_actions if a not in _CLOSED_WHEN_PUBLISHED
            ]
        return self


class ReportRequirementRow(BaseModel):
    id: UUID4
    name: str
    parent_id: Optional[UUID4] = None
    level: int
    coverage: Literal["tested", "errored_only", "not_in_runs", "no_tests"]
    tests: int
    passed: int
    failed: int
    errored: int
    pass_rate: Optional[float] = None


class ReportRunRow(BaseModel):
    id: UUID4
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    user_id: Optional[UUID4] = None
    results: int
    version_info: Optional[Dict[str, Any]] = None


class ReportTotals(BaseModel):
    results: int
    passed: int
    failed: int
    inconclusive: int
    errored: int
    pass_rate: Optional[float] = None
    requirements_tested: int
    requirements_total: int


class ReportMetrics(BaseModel):
    """The numbers core computes; the same shape live (draft) and frozen (published)."""

    result_rule: Literal["latest"] = "latest"
    totals: ReportTotals
    requirements: List[ReportRequirementRow]
    runs: List[ReportRunRow]
    versions_differ: bool = False


class ReportDetail(Report):
    test_run_ids: List[UUID4] = Field(default_factory=list)
    requirement_ids: List[UUID4] = Field(default_factory=list)
    metrics: Optional[ReportMetrics] = None
    # Output of the report sections the org is entitled to, keyed by section.
    sections: Dict[str, Any] = Field(default_factory=dict)

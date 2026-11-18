from datetime import datetime
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import UUID4, AliasChoices, BaseModel, ConfigDict, Field, model_validator

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.schemas.affordances import WithPermittedActions
from rhesis.backend.app.schemas.base import Base, BulkIds, ServerIdentity
from rhesis.backend.app.schemas.user import UserReference

ReportRecommendation = Literal["ready", "ready_with_risks", "not_ready"]
ReportStatus = Literal["draft", "published"]
# latest: the newest run's result per test. all: every result in every run (averages
# over repeated runs). worst: a test fails if it failed in any run.
ReportResultRule = Literal["latest", "all", "worst"]

# Actions a published report no longer offers, whatever the caller's role.
_CLOSED_WHEN_PUBLISHED = ("report:update", "report:delete", "report:publish")


class ReportBase(Base):
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = None
    recommendation: Optional[ReportRecommendation] = None
    result_rule: ReportResultRule = "latest"
    is_release: bool = True
    run_tag: Optional[str] = Field(default=None, max_length=100)
    baseline_report_id: Optional[UUID4] = None


class ReportCreate(ReportBase):
    endpoint_id: UUID4
    test_run_ids: BulkIds = Field(default_factory=list)
    requirement_ids: BulkIds = Field(default_factory=list)


class ReportUpdate(Base):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = None
    recommendation: Optional[ReportRecommendation] = None
    result_rule: Optional[ReportResultRule] = None
    is_release: Optional[bool] = None
    run_tag: Optional[str] = Field(default=None, max_length=100)
    baseline_report_id: Optional[UUID4] = None
    test_run_ids: Optional[BulkIds] = None
    requirement_ids: Optional[BulkIds] = None

    @model_validator(mode="after")
    def _required_stay_set(self) -> "ReportUpdate":
        # Omit a field to keep it; these columns can't be emptied.
        nulled = [
            name
            for name in ("title", "result_rule", "is_release")
            if name in self.model_fields_set and getattr(self, name) is None
        ]
        if nulled:
            raise ValueError(f"{', '.join(nulled)} can't be null; leave it out to keep it")
        return self


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
    # A published report names the endpoint as it was when published.
    endpoint: Optional[ReportEndpointRef] = Field(
        None, validation_alias=AliasChoices("endpoint_ref", "endpoint")
    )

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
    description: Optional[str] = None
    parent_id: Optional[UUID4] = None
    level: int
    coverage: Literal["tested", "errored_only", "not_in_runs", "no_tests"]
    tests: int
    passed: int
    failed: int
    errored: int
    pass_rate: Optional[float] = None
    # Tests whose verdict differed between runs (all and worst rules only).
    inconsistent: int = 0
    # Judged on fewer than LOW_SAMPLE results: read the pass rate with care.
    low_sample: bool = False
    # Change against the previous published report, in percentage points.
    pass_rate_delta: Optional[float] = None


class ReportRunExperiment(BaseModel):
    """The experiment whose parameters a run used, as snapshotted on the run."""

    id: Optional[UUID4] = None
    name: str
    version: str = ""


class ReportRunRow(BaseModel):
    id: UUID4
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    user_id: Optional[UUID4] = None
    results: int
    # The run's own pass rate over all its results, whatever the counting rule.
    pass_rate: Optional[float] = None
    status: Optional[str] = None
    test_set: Optional[str] = None
    version_info: Optional[Dict[str, Any]] = None
    experiment: Optional[ReportRunExperiment] = None


class ReportTotals(BaseModel):
    results: int
    passed: int
    failed: int
    inconclusive: int
    errored: int
    pass_rate: Optional[float] = None
    requirements_tested: int
    requirements_total: int
    inconsistent: int = 0


class ReportWarning(BaseModel):
    kind: str
    text: str


class ReportMetricResult(BaseModel):
    name: str
    # llm: an LLM judge; jev: a classifier with a Jev decision model; code: a code check.
    kind: Literal["llm", "jev", "code"]
    passed: int
    failed: int
    pass_rate: Optional[float] = None


class ReportRequirementMetrics(BaseModel):
    requirement_id: UUID4
    name: str
    level: int
    metrics: List[ReportMetricResult]


class ReportBaselineRef(BaseModel):
    id: UUID4
    title: str
    published_at: Optional[datetime] = None
    result_rule: ReportResultRule = "latest"


class ReportComparison(BaseModel):
    baseline: ReportBaselineRef
    pass_rate_delta: Optional[float] = None
    newly_failing: int = 0
    fixed: int = 0
    newly_failing_requirements: List[str] = Field(default_factory=list)


class ReportMetrics(BaseModel):
    """The numbers core computes; the same shape live (draft) and frozen (published)."""

    result_rule: ReportResultRule = "latest"
    totals: ReportTotals
    requirements: List[ReportRequirementRow]
    runs: List[ReportRunRow]
    versions_differ: bool = False
    warnings: List[ReportWarning] = Field(default_factory=list)
    comparison: Optional[ReportComparison] = None
    metric_results: List[ReportRequirementMetrics] = Field(default_factory=list)


class ReportDetail(Report):
    test_run_ids: List[UUID4] = Field(default_factory=list)
    # Runs that join a draft through its run tag (not picked by hand).
    tagged_run_ids: List[UUID4] = Field(default_factory=list)
    requirement_ids: List[UUID4] = Field(default_factory=list)
    metrics: Optional[ReportMetrics] = None
    # Output of the report sections the org is entitled to, keyed by section.
    sections: Dict[str, Any] = Field(default_factory=dict)

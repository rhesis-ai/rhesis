"""The verdict matrix: metric rows grouped by requirement, one encoded string
of per-test verdicts per row. See ``services/test_run.py:get_verdict_matrix``.

Cell alphabet, one character per test per metric row:
    ``.`` pending   ``P`` passed   ``F`` failed
    ``S`` scored (no pass/fail threshold)   ``E`` error   ``X`` not applicable
"""

from typing import List, Optional

from pydantic import UUID4, BaseModel, Field

from rhesis.backend.app.schemas.base import Base


class VerdictKpis(BaseModel):
    pass_rate: Optional[float] = None
    tests_executed: int = 0
    tests_total: int = 0
    verdicts_resolved: int = 0
    verdicts_planned: int = 0
    failures: int = 0
    reviews_count: int = 0


class VerdictRequirement(BaseModel):
    id: Optional[UUID4] = None
    name: str
    metric_keys: List[str]


class VerdictRow(BaseModel):
    requirement_id: Optional[UUID4] = None
    metric_key: str
    metric_name: str
    metric_id: Optional[UUID4] = None
    ambiguous: bool = False
    verdicts: str
    overrides: str
    passed: int = 0
    failed: int = 0
    pending: int = 0


class VerdictMatrix(Base):
    test_run_id: UUID4
    project_id: Optional[UUID4] = None
    status: str
    is_terminal: bool
    version: int = 0
    test_ids: Optional[List[UUID4]] = None
    test_status: str = ""
    # Execution phase offsets, in deciseconds from this run's timing origin,
    # aligned to test_ids' order (None where a phase wasn't reached or wasn't
    # recorded). They drive the Summary grid's animation; when absent the grid
    # renders settled. Sequential execution never reports a generating->
    # evaluating boundary, so test_generated_ds is empty for those runs.
    test_started_ds: Optional[List[Optional[int]]] = None
    test_generated_ds: Optional[List[Optional[int]]] = None
    test_resolved_ds: Optional[List[Optional[int]]] = None
    # How far into the run the server is right now, same units and origin.
    # Computed server-side so the client never has to reconcile clock skew.
    elapsed_ds: Optional[int] = None
    requirements: List[VerdictRequirement] = Field(default_factory=list)
    rows: List[VerdictRow] = Field(default_factory=list)
    kpis: VerdictKpis = Field(default_factory=VerdictKpis)

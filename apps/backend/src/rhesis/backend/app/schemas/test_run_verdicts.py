"""The verdict matrix: metric rows grouped by requirement, one encoded string
of per-test verdicts per row. See ``services/test_run.py:get_verdict_matrix``.

Cell alphabet, one character per test per metric row:
    ``.`` pending   ``P`` passed   ``F`` failed
    ``S`` scored (no pass/fail threshold)   ``E`` error   ``X`` not applicable
"""

from typing import List, Optional

from pydantic import UUID4, BaseModel

from rhesis.backend.app.schemas.base import Base


class VerdictKpis(BaseModel):
    pass_rate: Optional[float] = None
    tests_executed: int = 0
    tests_total: int = 0
    verdicts_resolved: int = 0
    verdicts_planned: int = 0
    failures: int = 0


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
    requirements: List[VerdictRequirement] = []
    rows: List[VerdictRow] = []
    kpis: VerdictKpis = VerdictKpis()

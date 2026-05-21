"""Preflight check request and response schemas."""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PreflightMode(str, Enum):
    ASYNC = "async"
    SYNC = "sync"


class PreflightCheckStatus(str, Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class PreflightMetricRef(BaseModel):
    id: UUID
    name: str
    scope: Optional[List[str]] = None


class PreflightCheckRequest(BaseModel):
    test_set_id: Optional[UUID] = None
    test_set_ids: Optional[List[UUID]] = None
    endpoint_id: UUID
    correlation_id: Optional[str] = None
    scoring_target: str = "fresh"
    metric_mode: str = "use_behavior"
    selected_metrics: Optional[List[PreflightMetricRef]] = None
    execution_model_id: Optional[str] = None
    evaluation_model_id: Optional[str] = None
    mode: PreflightMode = PreflightMode.ASYNC

    @model_validator(mode="after")
    def ensure_test_set_ids(self):
        if self.test_set_ids and len(self.test_set_ids) > 0:
            if self.test_set_id is None:
                self.test_set_id = self.test_set_ids[0]
        elif self.test_set_id is not None:
            self.test_set_ids = [self.test_set_id]
        else:
            raise ValueError(
                "Either test_set_id or test_set_ids must be provided"
            )
        return self


class PreflightCheckInfo(BaseModel):
    check_id: str
    label: str
    applicable: bool
    test_set_id: Optional[str] = None
    test_set_name: Optional[str] = None
    composite_key: Optional[str] = None


class PreflightCheckResult(BaseModel):
    check_id: str
    label: str
    status: PreflightCheckStatus
    message: Optional[str] = None
    detail: Optional[str] = None
    test_set_id: Optional[str] = None
    test_set_name: Optional[str] = None
    composite_key: Optional[str] = None


class PreflightCheckResponse(BaseModel):
    """Returned for async mode (202)."""

    correlation_id: str
    checks: List[PreflightCheckInfo]


class PreflightSyncResponse(BaseModel):
    """Returned for sync mode (200)."""

    checks: List[PreflightCheckResult]
    summary: str = Field(
        description="Overall result: passed, failed, or warning"
    )
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    skipped: int = 0

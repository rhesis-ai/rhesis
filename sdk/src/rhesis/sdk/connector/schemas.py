"""Pydantic schemas for connector messages."""

# NOTE: Counterpart at apps/backend/src/rhesis/backend/app/services/connector/schemas.py
# Keep in sync - these define the WebSocket wire protocol.

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    """Test execution status values."""

    SUCCESS = "success"
    ERROR = "error"


class FunctionParameter(BaseModel):
    """Function parameter schema."""

    name: str
    type: str
    default: Optional[str] = None


class FunctionMetadata(BaseModel):
    """Metadata about a collaborative function."""

    name: str
    parameters: Dict[str, Dict[str, Any]]
    return_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegisterMessage(BaseModel):
    """Message sent from SDK to backend to register functions and metrics.

    ``project_id`` and ``environment`` are optional so that an SDK can
    connect for metrics-only evaluation without a project binding.
    Old backends that require these fields will still receive them when
    the SDK is configured with a project.
    """

    type: str = "register"
    project_id: Optional[str] = None
    environment: Optional[str] = None
    sdk_version: str = "0.4.2"
    functions: List[FunctionMetadata]
    metrics: List["MetricMetadata"] = Field(default_factory=list)


class ExecuteTestMessage(BaseModel):
    """Message sent from backend to SDK to execute a test."""

    type: str = "execute_test"
    test_run_id: str
    function_name: str
    inputs: Dict[str, Any]


class TestResultMessage(BaseModel):
    """Message sent from SDK to backend with test results."""

    type: str = "test_result"
    test_run_id: str
    status: TestStatus  # Validated enum: "success" or "error"
    output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float
    trace_id: Optional[str] = None  # 32-char hex trace ID for linking to traces


class MetricMetadata(BaseModel):
    """Metadata about an SDK-registered metric."""

    name: str
    parameters: List[str] = Field(
        description="Parameter names this metric accepts (subset of the allowed set)"
    )
    return_type: str = "MetricResult"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecuteMetricMessage(BaseModel):
    """Message sent from backend to SDK to execute a metric."""

    type: str = "execute_metric"
    metric_run_id: str
    metric_name: str
    inputs: Dict[str, Any]


class MetricResultMessage(BaseModel):
    """Message sent from SDK to backend with metric evaluation results."""

    type: str = "metric_result"
    metric_run_id: str
    status: TestStatus
    score: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float


class PingMessage(BaseModel):
    """Ping message for keepalive."""

    type: str = "ping"


class PongMessage(BaseModel):
    """Pong response to ping."""

    type: str = "pong"


# Resolve forward references for RegisterMessage -> MetricMetadata
RegisterMessage.model_rebuild()

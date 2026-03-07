"""Pydantic schemas for connector service."""

# NOTE: Counterpart at sdk/src/rhesis/sdk/connector/schemas.py
# Keep in sync - these define the WebSocket wire protocol.

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class WebSocketConnectionContext:
    """Immutable context for an authenticated WebSocket connection.

    Created at connection time from the authenticated user. The organization_id
    and user_id cannot be overridden by subsequent messages — they are derived
    solely from the authentication token.
    """

    connection_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str = ""
    organization_id: str = ""


class FunctionMetadata(BaseModel):
    """Metadata about a collaborative function."""

    name: str
    parameters: Dict[str, Dict[str, Any]]
    return_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricMetadata(BaseModel):
    """Metadata about an SDK-registered metric."""

    name: str
    parameters: List[str] = Field(default_factory=list)
    return_type: str = "MetricResult"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegisterMessage(BaseModel):
    """Message received from SDK to register functions and metrics."""

    type: str = "register"
    project_id: Optional[str] = None
    environment: Optional[str] = None
    sdk_version: str
    functions: List[FunctionMetadata]
    metrics: List[MetricMetadata] = Field(default_factory=list)


class ExecuteTestMessage(BaseModel):
    """Message sent to SDK to execute a test."""

    type: str = "execute_test"
    test_run_id: str
    function_name: str
    inputs: Dict[str, Any]


class ExecuteMetricMessage(BaseModel):
    """Message sent to SDK to execute a metric."""

    type: str = "execute_metric"
    metric_run_id: str
    metric_name: str
    inputs: Dict[str, Any]


class TestResultMessage(BaseModel):
    """Message received from SDK with test results."""

    type: str = "test_result"
    test_run_id: str
    status: str  # "success" or "error"
    output: Optional[Any] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None
    duration_ms: float


class MetricResultMessage(BaseModel):
    """Message received from SDK with metric evaluation results."""

    type: str = "metric_result"
    metric_run_id: str
    status: str  # "success" or "error"
    score: Optional[Any] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float


class ConnectionStatus(BaseModel):
    """Connection status for a project."""

    project_id: str
    environment: str
    connected: bool
    functions: List[FunctionMetadata] = Field(default_factory=list)

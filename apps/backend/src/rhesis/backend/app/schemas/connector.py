"""Schemas for connector REST API."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from rhesis.backend.app.services.connector.schemas import ConnectionStatus


class TriggerTestRequest(BaseModel):
    """Request to trigger a test execution."""

    project_id: str = Field(..., description="Project identifier")
    environment: str = Field(default="development", description="Environment name")
    function_name: str = Field(..., description="Function to execute")
    inputs: Dict[str, Any] = Field(..., description="Function inputs")


class TriggerTestResponse(BaseModel):
    """Response after triggering a test."""

    success: bool = Field(..., description="Whether request was sent successfully")
    test_run_id: str = Field(..., description="Test run identifier")
    message: str = Field(..., description="Status message")


class ConnectionStatusResponse(ConnectionStatus):
    """Response for connection status check."""

    pass


class ExecutionTrace(BaseModel):
    """Execution trace from SDK for observability."""

    function_name: str = Field(..., description="Name of the executed function")
    inputs: Dict[str, Any] = Field(..., description="Function inputs")
    output: Optional[str] = Field(None, description="Function output")
    duration_ms: float = Field(..., description="Execution duration in milliseconds")
    status: str = Field(..., description="Execution status: success or error")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: float = Field(..., description="Unix timestamp of execution")
    project_id: str = Field(..., description="Project identifier")
    environment: str = Field(..., description="Environment name")


class TraceResponse(BaseModel):
    """Response after receiving a trace."""

    status: str = Field(default="received", description="Status message")

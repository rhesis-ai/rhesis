"""Pydantic schemas for connector service."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FunctionMetadata(BaseModel):
    """Metadata about a collaborative function."""

    name: str
    parameters: Dict[str, Dict[str, Any]]
    return_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegisterMessage(BaseModel):
    """Message received from SDK to register functions."""

    type: str = "register"
    project_id: str
    environment: str
    sdk_version: str
    functions: List[FunctionMetadata]


class ExecuteTestMessage(BaseModel):
    """Message sent to SDK to execute a test."""

    type: str = "execute_test"
    test_run_id: str
    function_name: str
    inputs: Dict[str, Any]


class TestResultMessage(BaseModel):
    """Message received from SDK with test results."""

    type: str = "test_result"
    test_run_id: str
    status: str  # "success" or "error"
    output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float


class ConnectionStatus(BaseModel):
    """Connection status for a project."""

    project_id: str
    environment: str
    connected: bool
    functions: List[FunctionMetadata] = Field(default_factory=list)

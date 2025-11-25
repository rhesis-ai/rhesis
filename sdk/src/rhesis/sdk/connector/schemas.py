"""Pydantic schemas for connector messages."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    """Message sent from SDK to backend to register functions."""

    type: str = "register"
    project_id: str
    environment: str
    sdk_version: str = "0.4.2"
    functions: List[FunctionMetadata]


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
    status: str  # "success" or "error"
    output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float


class PingMessage(BaseModel):
    """Ping message for keepalive."""

    type: str = "ping"


class PongMessage(BaseModel):
    """Pong response to ping."""

    type: str = "pong"

"""Shared fixtures for Penelope tests."""

import os
from unittest.mock import Mock

import pytest

# Mock OpenAI API key to prevent DeepEval from failing during imports
# This is needed because the SDK imports DeepEval metrics which try to initialize OpenAI clients
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "mock-api-key-for-testing"
from rhesis.penelope.targets.base import Target, TargetResponse
from rhesis.penelope.tools.base import Tool, ToolResult

from rhesis.sdk.models.base import BaseLLM


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    mock = Mock(spec=BaseLLM)
    mock.generate.return_value = {
        "reasoning": "Test reasoning",
        "tool_name": "test_tool",
        "parameters": {},
    }
    mock.get_model_name.return_value = "MockLLM"
    return mock


@pytest.fixture
def mock_target():
    """Create a mock Target instance."""

    class MockTarget(Target):
        @property
        def target_type(self) -> str:
            return "mock"

        @property
        def target_id(self) -> str:
            return "mock-target-123"

        @property
        def description(self) -> str:
            return "Mock target for testing"

        def send_message(self, message: str, session_id=None, **kwargs):
            return TargetResponse(
                success=True,
                content="Mock response",
                session_id=session_id or "session-123",
            )

        def validate_configuration(self):
            return True, None

    return MockTarget()


@pytest.fixture
def mock_tool():
    """Create a mock Tool instance."""

    class MockTool(Tool):
        @property
        def name(self) -> str:
            return "mock_tool"

        @property
        def description(self) -> str:
            return "Mock tool for testing"

        def execute(self, **kwargs):
            return ToolResult(success=True, output={"result": "mock result"})

    return MockTool()


@pytest.fixture
def sample_test_context():
    """Create a sample TestContext for testing."""
    from rhesis.penelope.context import TestContext

    return TestContext(
        target_id="test-target-123",
        target_type="endpoint",
        instructions="Test the chatbot",
        goal="Verify responses are accurate",
        scenario="Testing scenario",
        context={"test": "data"},
        max_turns=10,
    )


@pytest.fixture
def sample_test_state(sample_test_context):
    """Create a sample TestState for testing."""
    from rhesis.penelope.context import TestState

    return TestState(context=sample_test_context)

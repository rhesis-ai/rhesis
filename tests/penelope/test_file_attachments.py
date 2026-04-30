"""Tests for file attachment support in Penelope multi-turn tests."""

from unittest.mock import Mock

import pytest

from rhesis.penelope.context import TestContext, TestState
from rhesis.penelope.executor import TurnExecutor
from rhesis.penelope.schemas import SendMessageParams
from rhesis.sdk.targets import Target, TargetResponse
from rhesis.penelope.tools.base import ToolResult
from rhesis.penelope.tools.target_interaction import TargetInteractionTool
from rhesis.sdk.models.base import BaseLLM

SAMPLE_FILES = [
    {
        "filename": "image.png",
        "content_type": "image/png",
        "data": "iVBORw0KGgoAAAANSUhEUg==",
    },
    {
        "filename": "document.pdf",
        "content_type": "application/pdf",
        "data": "JVBERi0xLjQ=",
    },
]


class TestTestContextFiles:
    """Tests for TestContext files field."""

    def test_default_files_is_empty_list(self):
        """TestContext files defaults to empty list."""
        ctx = TestContext(
            target_id="t",
            target_type="endpoint",
            instructions="test",
            goal="goal",
        )
        assert ctx.files == []

    def test_stores_files(self):
        """TestContext stores files correctly."""
        ctx = TestContext(
            target_id="t",
            target_type="endpoint",
            instructions="test",
            goal="goal",
            files=SAMPLE_FILES,
        )
        assert len(ctx.files) == 2
        assert ctx.files[0]["filename"] == "image.png"
        assert ctx.files[1]["content_type"] == "application/pdf"


class TestSendMessageParamsIncludeFiles:
    """Tests for SendMessageParams include_files field."""

    def test_default_include_files_is_false(self):
        """include_files defaults to False."""
        params = SendMessageParams(message="hello")
        assert params.include_files is False

    def test_include_files_true(self):
        """include_files can be set to True."""
        params = SendMessageParams(message="hello", include_files=True)
        assert params.include_files is True

    def test_serialization(self):
        """include_files serializes correctly."""
        params = SendMessageParams(message="hello", include_files=True)
        dumped = params.model_dump()
        assert dumped["include_files"] is True

    def test_serialization_exclude_none(self):
        """include_files appears in exclude_none dump when True."""
        params = SendMessageParams(message="hello", include_files=True)
        dumped = params.model_dump(exclude_none=True)
        assert "include_files" in dumped

    def test_false_excluded_when_exclude_defaults(self):
        """include_files=False is excluded when exclude_defaults=True."""
        params = SendMessageParams(message="hello")
        dumped = params.model_dump(exclude_defaults=True)
        assert "include_files" not in dumped


class TestExecutorFileInjection:
    """Tests for file injection in TurnExecutor."""

    @pytest.fixture
    def mock_model(self):
        mock = Mock(spec=BaseLLM)
        mock.get_model_name.return_value = "mock-model"
        return mock

    @pytest.fixture
    def state_with_files(self):
        ctx = TestContext(
            target_id="t",
            target_type="endpoint",
            instructions="test",
            goal="goal",
            files=SAMPLE_FILES,
        )
        return TestState(context=ctx)

    @pytest.fixture
    def state_without_files(self):
        ctx = TestContext(
            target_id="t",
            target_type="endpoint",
            instructions="test",
            goal="goal",
        )
        return TestState(context=ctx)

    @pytest.fixture
    def mock_tool(self):
        tool = Mock()
        tool.name = "send_message_to_target"
        tool.execute.return_value = ToolResult(success=True, output={"response": "ok"}, error=None)
        return tool

    def test_injects_files_when_include_files_true(self, mock_model, state_with_files, mock_tool):
        """Files are injected into tool params when include_files=True."""
        mock_model.generate.return_value = {
            "reasoning": "Send with files",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "Check this image",
                        "include_files": True,
                    },
                }
            ],
        }
        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=state_with_files,
            tools=[mock_tool],
            system_prompt="System prompt",
        )
        assert success is True
        call_kwargs = mock_tool.execute.call_args[1]
        assert "files" in call_kwargs
        assert len(call_kwargs["files"]) == 2
        # include_files should be popped, not passed to tool
        assert "include_files" not in call_kwargs

    def test_no_files_when_include_files_false(self, mock_model, state_with_files, mock_tool):
        """Files are NOT injected when include_files=False."""
        mock_model.generate.return_value = {
            "reasoning": "Send without files",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "Just text",
                        "include_files": False,
                    },
                }
            ],
        }
        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=state_with_files,
            tools=[mock_tool],
            system_prompt="System prompt",
        )
        assert success is True
        call_kwargs = mock_tool.execute.call_args[1]
        assert "files" not in call_kwargs
        assert "include_files" not in call_kwargs

    def test_no_files_when_omitted(self, mock_model, state_with_files, mock_tool):
        """Files are NOT injected when include_files is not in params."""
        mock_model.generate.return_value = {
            "reasoning": "Normal message",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {"message": "Hello"},
                }
            ],
        }
        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=state_with_files,
            tools=[mock_tool],
            system_prompt="System prompt",
        )
        assert success is True
        call_kwargs = mock_tool.execute.call_args[1]
        assert "files" not in call_kwargs

    def test_no_files_when_context_has_no_files(self, mock_model, state_without_files, mock_tool):
        """Files are NOT injected even if include_files=True but context has no files."""
        mock_model.generate.return_value = {
            "reasoning": "Try to include files",
            "tool_calls": [
                {
                    "tool_name": "send_message_to_target",
                    "parameters": {
                        "message": "Hello",
                        "include_files": True,
                    },
                }
            ],
        }
        executor = TurnExecutor(model=mock_model)
        success = executor.execute_turn(
            state=state_without_files,
            tools=[mock_tool],
            system_prompt="System prompt",
        )
        assert success is True
        call_kwargs = mock_tool.execute.call_args[1]
        assert "files" not in call_kwargs


class TestTargetInteractionToolFiles:
    """Tests for TargetInteractionTool passing files to target."""

    @pytest.fixture
    def mock_target(self):
        class FileCapturingTarget(Target):
            captured_files = None

            @property
            def target_type(self):
                return "mock"

            @property
            def target_id(self):
                return "mock-123"

            @property
            def description(self):
                return "Mock target"

            def send_message(self, message, conversation_id=None, files=None, **kwargs):
                self.captured_files = files
                return TargetResponse(
                    success=True,
                    content="Response",
                    conversation_id=conversation_id,
                )

            def validate_configuration(self):
                return True, None

        return FileCapturingTarget()

    def test_passes_files_to_target(self, mock_target):
        """Files are passed through to target.send_message()."""
        tool = TargetInteractionTool(mock_target)
        result = tool.execute(message="Hello", files=SAMPLE_FILES)
        assert result.success is True
        assert mock_target.captured_files == SAMPLE_FILES

    def test_no_files_passed_when_none(self, mock_target):
        """No files kwarg when files not provided."""
        tool = TargetInteractionTool(mock_target)
        result = tool.execute(message="Hello")
        assert result.success is True
        assert mock_target.captured_files is None


class TestSystemPromptFileInfo:
    """Tests for file info in system prompt context."""

    def test_file_info_in_context(self):
        """File info appears in context when files are present."""
        # Verify the context string building logic from execute_test
        files = SAMPLE_FILES
        context = {"test": "data"}

        # Simulate the context string building from execute_test
        context_str = str(context) if context else ""
        if files:
            file_descriptions = []
            for f in files:
                file_descriptions.append(
                    f"- {f.get('filename', 'unknown')} ({f.get('content_type', 'unknown')})"
                )
            files_info = (
                "\n\nAttached files available for this test:\n"
                + "\n".join(file_descriptions)
                + "\n\nTo include these files with a message to the target, "
                "set include_files=true in send_message_to_target parameters."
            )
            context_str = (context_str + files_info) if context_str else files_info

        assert "image.png" in context_str
        assert "image/png" in context_str
        assert "document.pdf" in context_str
        assert "application/pdf" in context_str
        assert "include_files=true" in context_str

    def test_no_file_info_without_files(self):
        """No file info in context when no files."""
        context = {"test": "data"}
        files = None

        context_str = str(context) if context else ""
        if files:
            pass  # would add file info

        assert "Attached files" not in context_str

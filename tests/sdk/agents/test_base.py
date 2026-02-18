"""Tests for BaseAgent class."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from rhesis.sdk.agents.base import BaseAgent, BaseTool, MCPTool
from rhesis.sdk.agents.schemas import ExecutionStep, ToolCall, ToolResult
from rhesis.sdk.models.base import BaseLLM

# ── helpers ────────────────────────────────────────────────────────


class DummyTool(BaseTool):
    """Concrete BaseTool for testing."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool"

    @property
    def parameters_schema(self) -> dict:
        return {"properties": {"x": {"type": "string"}}}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(tool_name="dummy", success=True, content="ok")


def _make_agent(
    mock_model,
    tools=None,
    max_iterations=5,
    max_tool_executions=None,
    timeout_seconds=None,
    history_window=None,
):
    return BaseAgent(
        model=mock_model,
        tools=tools or [],
        max_iterations=max_iterations,
        max_tool_executions=max_tool_executions,
        timeout_seconds=timeout_seconds,
        history_window=history_window,
        verbose=False,
    )


def _finish_dict(answer="Done"):
    return {
        "reasoning": "Finished",
        "action": "finish",
        "tool_calls": [],
        "final_answer": answer,
    }


def _tool_dict(tool_name="dummy", args=None):
    return {
        "reasoning": "Calling tool",
        "action": "call_tool",
        "tool_calls": [
            {
                "tool_name": tool_name,
                "arguments": json.dumps(args or {}),
            }
        ],
        "final_answer": None,
    }


# ── tests ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBaseAgentInit:
    """Test BaseAgent initialization."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    def test_default_parameters(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent.max_iterations == 5
        assert agent._max_tool_executions == 15
        assert agent._timeout_seconds is None
        assert agent._history_window == 20
        assert agent._tools == []
        assert agent._execution_history == []

    def test_custom_parameters(self, mock_model):
        agent = _make_agent(
            mock_model,
            max_iterations=10,
            max_tool_executions=5,
            timeout_seconds=30.0,
            history_window=10,
        )
        assert agent.max_iterations == 10
        assert agent._max_tool_executions == 5
        assert agent._timeout_seconds == 30.0
        assert agent._history_window == 10

    def test_has_turn_lock(self, mock_model):
        agent = _make_agent(mock_model)
        assert hasattr(agent, "_turn_lock")


@pytest.mark.unit
class TestBaseAgentToolRouting:
    """Test default tool routing."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_base_tool_dispatch(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])

        tc = ToolCall(tool_name="dummy", arguments="{}")
        result = await agent.execute_tool(tc)

        assert result.success
        assert result.content == "ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_not_found(self, mock_model):
        agent = _make_agent(mock_model)

        tc = ToolCall(tool_name="nonexistent", arguments="{}")
        result = await agent.execute_tool(tc)

        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_mcp_tool_dispatch(self, mock_model):
        mcp = Mock(spec=MCPTool)
        mcp.execute = AsyncMock(
            return_value=ToolResult(
                tool_name="search",
                success=True,
                content="results",
            )
        )
        mcp.list_tools = AsyncMock(return_value=[])
        agent = _make_agent(mock_model, tools=[mcp])

        tc = ToolCall(tool_name="search", arguments='{"q": "hi"}')
        result = await agent.execute_tool(tc)

        assert result.success
        assert result.content == "results"

    @pytest.mark.asyncio
    async def test_get_available_tools_aggregates(self, mock_model):
        base_tool = DummyTool()
        mcp = Mock(spec=MCPTool)
        mcp.list_tools = AsyncMock(
            return_value=[{"name": "mcp_tool", "description": "An MCP tool"}]
        )
        agent = _make_agent(mock_model, tools=[base_tool, mcp])

        tools = await agent.get_available_tools()
        names = [t["name"] for t in tools]

        assert "dummy" in names
        assert "mcp_tool" in names


@pytest.mark.unit
class TestBaseAgentRunLoop:
    """Test _run_loop failsafes."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_finish_returns_answer(self, mock_model):
        agent = _make_agent(mock_model)
        mock_model.generate.return_value = _finish_dict("hello")

        result = await agent.run_async("hi")
        assert result.success
        assert result.final_answer == "hello"

    @pytest.mark.asyncio
    async def test_max_iterations_failsafe(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool], max_iterations=2)
        mock_model.generate.return_value = _tool_dict()

        result = await agent.run_async("go")
        assert "maximum number of internal iterations" in result.final_answer

    @pytest.mark.asyncio
    async def test_timeout_failsafe(self, mock_model):
        agent = _make_agent(mock_model, max_iterations=100, timeout_seconds=0.0)
        mock_model.generate.return_value = _tool_dict()

        result = await agent.run_async("go")
        assert "run out of time" in result.final_answer

    @pytest.mark.asyncio
    async def test_max_tool_executions_failsafe(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(
            mock_model,
            tools=[tool],
            max_iterations=100,
            max_tool_executions=2,
        )
        mock_model.generate.return_value = _tool_dict()

        result = await agent.run_async("go")
        assert "maximum number of tool calls" in result.final_answer


@pytest.mark.unit
class TestBaseAgentHistoryWindowing:
    """Test _format_history windowing."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    def test_window_truncation(self, mock_model):
        agent = _make_agent(mock_model, history_window=2)

        for i in range(5):
            agent._execution_history.append(
                ExecutionStep(
                    iteration=i,
                    reasoning=f"step {i}",
                    action="call_tool",
                    tool_calls=[],
                    tool_results=[],
                )
            )

        formatted = agent._format_history()
        assert "step 3" in formatted
        assert "step 4" in formatted
        assert "step 0" not in formatted
        assert "earlier tool steps omitted" in formatted

    def test_result_content_truncation(self, mock_model):
        agent = _make_agent(mock_model, history_window=10)
        long_content = "x" * 500
        agent._execution_history.append(
            ExecutionStep(
                iteration=1,
                reasoning="test",
                action="call_tool",
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="t",
                        success=True,
                        content=long_content,
                    )
                ],
            )
        )

        formatted = agent._format_history()
        # Content should be truncated to 300 chars
        assert "x" * 300 in formatted
        assert "x" * 301 not in formatted

    def test_empty_history(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent._format_history() == ""


@pytest.mark.unit
class TestToolCallSchema:
    """Test ToolCall.arguments round-trips correctly."""

    def test_json_string_parsed_to_dict(self):
        tc = ToolCall(tool_name="test", arguments='{"x": 1}')
        assert tc.arguments == {"x": 1}

    def test_dict_passed_through(self):
        tc = ToolCall(tool_name="test", arguments={"x": 1})
        assert tc.arguments == {"x": 1}

    def test_model_dump_roundtrip(self):
        tc = ToolCall(tool_name="test", arguments='{"x": 1}')
        dumped = tc.model_dump()
        restored = ToolCall(**dumped)
        assert restored.arguments == {"x": 1}

    def test_empty_string_becomes_empty_dict(self):
        tc = ToolCall(tool_name="test", arguments="{}")
        assert tc.arguments == {}

    def test_invalid_json_becomes_empty_dict(self):
        tc = ToolCall(tool_name="test", arguments="not json")
        assert tc.arguments == {}

    def test_default_is_empty_dict(self):
        tc = ToolCall(tool_name="test")
        assert tc.arguments == {}

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
        model.a_generate = AsyncMock(return_value={})
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
        mock_model.a_generate.return_value = _finish_dict("hello")

        result = await agent.run_async("hi")
        assert result.success
        assert result.final_answer == "hello"

    @pytest.mark.asyncio
    async def test_max_iterations_failsafe(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool], max_iterations=2)
        mock_model.a_generate.return_value = _tool_dict()

        result = await agent.run_async("go")
        assert "maximum number of internal iterations" in result.final_answer

    @pytest.mark.asyncio
    async def test_timeout_failsafe(self, mock_model):
        agent = _make_agent(mock_model, max_iterations=100, timeout_seconds=0.0)
        mock_model.a_generate.return_value = _tool_dict()

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
        mock_model.a_generate.return_value = _tool_dict()

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
        long_content = "x" * 5000
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
        assert "x" * 4000 in formatted
        assert "x" * 4001 not in formatted

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

    def test_invalid_json_is_logged(self, caplog):
        """Silently dropping the payload makes the server's 422 unreadable."""
        with caplog.at_level("ERROR", logger="rhesis.sdk.agents.schemas"):
            ToolCall(tool_name="test", arguments="{broken")
        assert "not valid JSON" in caplog.text

    def test_valid_json_non_object_becomes_empty_dict(self):
        """A bare list parses fine but would otherwise fail ToolCall validation."""
        tc = ToolCall(tool_name="test", arguments="[1, 2]")
        assert tc.arguments == {}

    def test_default_is_empty_dict(self):
        tc = ToolCall(tool_name="test")
        assert tc.arguments == {}


@pytest.mark.unit
class TestFormatTools:
    """Test the tool descriptions rendered into the iteration prompt."""

    @pytest.fixture
    def agent(self):
        model = Mock(spec=BaseLLM)
        model.a_generate = AsyncMock(return_value={})
        return _make_agent(model)

    @staticmethod
    def _tool(properties, required=None):
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return [{"name": "t", "description": "d", "inputSchema": schema}]

    def test_no_tools(self, agent):
        assert agent._format_tools([]) == "(no tools available)"

    def test_top_level_params_and_required_flag(self, agent):
        out = agent._format_tools(
            self._tool({"name": {"type": "string", "description": "The name"}}, ["name"])
        )
        assert "name: string (required)  -- The name" in out

    def test_server_managed_fields_excluded(self, agent):
        out = agent._format_tools(self._tool({"id": {"type": "string"}, "x": {"type": "string"}}))
        assert "id:" not in out
        assert "x: string" in out

    def test_nested_id_is_kept(self, agent):
        """A nested 'id' is a reference, not a server-managed field.

        generate_test_set's sources items carry only an id — hiding it
        would contradict the tool description.
        """
        out = agent._format_tools(
            self._tool(
                {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"id": {"type": "string"}},
                            "required": ["id"],
                        },
                    }
                }
            )
        )
        assert "id: string (required)" in out

    def test_array_item_properties_are_expanded(self, agent):
        """The 'tests: array[object]' case — item fields must be visible."""
        out = agent._format_tools(
            self._tool(
                {
                    "tests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "behavior": {"type": "string"},
                                "category": {"type": "string"},
                            },
                            "required": ["behavior", "category"],
                        },
                    }
                },
                ["tests"],
            )
        )
        assert "tests: array[object] (required)" in out
        assert "Each item:" in out
        assert "behavior: string (required)" in out
        assert "category: string (required)" in out

    def test_nested_object_properties_are_expanded(self, agent):
        out = agent._format_tools(
            self._tool(
                {
                    "config": {
                        "type": "object",
                        "properties": {"generation_prompt": {"type": "string"}},
                    }
                }
            )
        )
        assert "generation_prompt: string" in out

    def test_optional_wrapper_is_unwrapped(self, agent):
        """Optional[Model] arrives as anyOf[Model, null] and must still expand."""
        out = agent._format_tools(
            self._tool(
                {
                    "prompt": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {"content": {"type": "string"}},
                                "required": ["content"],
                            },
                            {"type": "null"},
                        ]
                    }
                }
            )
        )
        assert "content: string (required)" in out

    def test_recursion_stops_at_max_depth(self, agent):
        """Three levels below the top — enough for tests[].prompt.content — then stop."""
        deep = {
            "type": "object",
            "properties": {
                "l1": {
                    "type": "object",
                    "properties": {
                        "l2": {
                            "type": "object",
                            "properties": {
                                "l3": {
                                    "type": "object",
                                    "properties": {"l4": {"type": "string"}},
                                }
                            },
                        }
                    },
                }
            },
        }
        out = agent._format_tools([{"name": "t", "description": "d", "inputSchema": deep}])
        assert "l1: object" in out
        assert "l2: object" in out
        assert "l3: object" in out
        assert "l4:" not in out

    def test_dict_any_object_has_nothing_to_expand(self, agent):
        """Dict[str, Any] renders as a bare object with no invented fields."""
        out = agent._format_tools(self._tool({"metadata": {"type": "object"}}))
        assert "metadata: object" in out
        assert "Each item:" not in out

    def test_enum_renders_literals(self, agent):
        out = agent._format_tools(
            self._tool({"test_type": {"type": "string", "enum": ["Single-Turn", "Multi-Turn"]}})
        )
        assert 'test_type: "Single-Turn" | "Multi-Turn"' in out

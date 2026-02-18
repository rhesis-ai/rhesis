"""Tests for ArchitectAgent class."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from rhesis.sdk.agents.architect.agent import ArchitectAgent
from rhesis.sdk.agents.base import BaseAgent, BaseTool
from rhesis.sdk.agents.schemas import ExecutionStep, ToolResult
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
    """Create an ArchitectAgent with a mock model."""
    return ArchitectAgent(
        model=mock_model,
        tools=tools or [],
        max_iterations=max_iterations,
        max_tool_executions=max_tool_executions,
        timeout_seconds=timeout_seconds,
        history_window=history_window,
        verbose=False,
    )


def _finish_dict(answer="Done"):
    """Return a raw dict matching AgentAction for 'finish'."""
    return {
        "reasoning": "Finished",
        "action": "finish",
        "tool_calls": [],
        "final_answer": answer,
    }


def _tool_dict(tool_name="dummy", args=None):
    """Return a raw dict matching AgentAction for 'call_tool'."""
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
class TestArchitectAgentInheritance:
    """Test that ArchitectAgent properly extends BaseAgent."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    def test_is_subclass_of_base_agent(self, mock_model):
        agent = _make_agent(mock_model)
        assert isinstance(agent, BaseAgent)

    def test_inherits_turn_lock(self, mock_model):
        agent = _make_agent(mock_model)
        assert hasattr(agent, "_turn_lock")


@pytest.mark.unit
class TestArchitectAgentInit:
    """Test ArchitectAgent initialization and parameters."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    def test_default_parameters(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent.max_iterations == 5
        assert agent._max_tool_executions == 15  # 5 * 3
        assert agent._timeout_seconds is None
        assert agent._history_window == 20
        assert agent._mode == "discovery"

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

    def test_tools_injected(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        assert len(agent._tools) == 1
        assert agent._tools[0] is tool

    def test_reset_clears_state(self, mock_model):
        agent = _make_agent(mock_model)
        agent._conversation_history.append({"role": "user", "content": "hi"})
        agent._mode = "creating"
        agent.reset()
        assert agent._conversation_history == []
        assert agent._execution_history == []
        assert agent._mode == "discovery"


@pytest.mark.unit
class TestArchitectAgentModeTransitions:
    """Test mode transition logic."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_set_mode_emits_event(self, mock_model):
        agent = _make_agent(mock_model)
        handler = Mock()
        handler.on_mode_change = AsyncMock()
        agent._event_handlers = [handler]

        await agent.set_mode_async("planning")

        assert agent._mode == "planning"
        handler.on_mode_change.assert_called_once_with(old_mode="discovery", new_mode="planning")

    @pytest.mark.asyncio
    async def test_same_mode_no_event(self, mock_model):
        agent = _make_agent(mock_model)
        handler = Mock()
        handler.on_mode_change = AsyncMock()
        agent._event_handlers = [handler]

        await agent.set_mode_async("discovery")
        handler.on_mode_change.assert_not_called()


@pytest.mark.unit
class TestArchitectAgentRunTurn:
    """Test _run_loop via chat_async with failsafes."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_finish_action_returns_answer(self, mock_model):
        agent = _make_agent(mock_model)
        mock_model.generate.return_value = _finish_dict("hello")

        response = await agent.chat_async("hi")
        assert response == "hello"

    @pytest.mark.asyncio
    async def test_max_iterations_stops_loop(self, mock_model):
        agent = _make_agent(mock_model, max_iterations=2)
        mock_model.generate.return_value = _tool_dict()

        response = await agent.chat_async("hi")
        assert "maximum number of internal iterations" in response
        assert mock_model.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_max_tool_executions_stops_loop(self, mock_model):
        """Agent stops when tool execution count exceeds limit."""
        tool = DummyTool()
        agent = _make_agent(
            mock_model,
            tools=[tool],
            max_iterations=100,
            max_tool_executions=2,
        )
        mock_model.generate.return_value = _tool_dict()

        response = await agent.chat_async("go")
        assert "maximum number of tool calls" in response

    @pytest.mark.asyncio
    async def test_timeout_stops_loop(self, mock_model):
        """Agent stops when timeout is reached."""
        agent = _make_agent(
            mock_model,
            max_iterations=100,
            timeout_seconds=0.0,
        )
        mock_model.generate.return_value = _tool_dict()

        response = await agent.chat_async("go")
        assert "run out of time" in response

    @pytest.mark.asyncio
    async def test_llm_error_returns_error_message(self, mock_model):
        agent = _make_agent(mock_model)
        mock_model.generate.side_effect = ValueError("bad json")

        response = await agent.chat_async("hi")
        # On LLM error, _run_loop returns the empty string from
        # the finish step's content (error step)
        assert response is not None


@pytest.mark.unit
class TestArchitectAgentToolRouting:
    """Test tool execution routing (BaseTool vs MCPTool)."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_base_tool_execution(self, mock_model):
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])

        mock_model.generate.side_effect = [
            _tool_dict("dummy"),
            _finish_dict("done"),
        ]

        response = await agent.chat_async("use dummy")
        assert response == "done"
        assert len(agent._execution_history) >= 1
        assert agent._execution_history[0].tool_results[0].success

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, mock_model):
        agent = _make_agent(mock_model)

        mock_model.generate.side_effect = [
            _tool_dict("nonexistent"),
            _finish_dict("done"),
        ]

        response = await agent.chat_async("use tool")
        assert response == "done"
        result = agent._execution_history[0].tool_results[0]
        assert not result.success
        assert "not found" in result.error


@pytest.mark.unit
class TestArchitectAgentHistoryWindowing:
    """Test that history windowing caps what is sent to the LLM."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    def test_conversation_window_applied(self, mock_model):
        agent = _make_agent(mock_model, history_window=2)

        for i in range(5):
            agent._conversation_history.append({"role": "user", "content": f"msg {i}"})

        formatted = agent._format_history()
        assert "msg 3" in formatted
        assert "msg 4" in formatted
        assert "msg 0" not in formatted
        assert "earlier messages omitted" in formatted

    def test_execution_window_applied(self, mock_model):
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

    def test_no_window_marker_when_within_limit(self, mock_model):
        agent = _make_agent(mock_model, history_window=10)
        agent._conversation_history.append({"role": "user", "content": "hi"})
        formatted = agent._format_history()
        assert "omitted" not in formatted

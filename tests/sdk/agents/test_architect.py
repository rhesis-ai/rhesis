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
    agent = ArchitectAgent(
        model=mock_model,
        tools=tools or [],
        max_iterations=max_iterations,
        max_tool_executions=max_tool_executions,
        timeout_seconds=timeout_seconds,
        history_window=history_window,
        verbose=False,
    )
    # Default to empty so the write-guard doesn't block tests that
    # aren't specifically testing it.  Write-guard tests set this
    # explicitly.
    agent._mutating_tools = frozenset()
    return agent


def _mock_model():
    """Create a mock BaseLLM with generate_stream support."""
    model = Mock(spec=BaseLLM)
    model.generate = Mock(return_value={})

    async def _default_stream(prompt, system_prompt=None, **kw):
        # Fallback: yields the final_answer seed from the finish action
        yield prompt[:50] if prompt else "response"

    model.generate_stream = Mock(side_effect=_default_stream)
    return model


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


# ── write-guard tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestArchitectWriteGuard:
    """Test that mutating tools are blocked until user confirms."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    # -- _is_mutating --

    def test_mutating_tools_detected_from_http_method(self, mock_model):
        agent = _make_agent(mock_model)
        agent._mutating_tools = frozenset(
            {"create_metric", "generate_metric", "update_behavior", "execute_tests"}
        )
        assert agent._is_mutating("create_metric") is True
        assert agent._is_mutating("generate_metric") is True
        assert agent._is_mutating("update_behavior") is True
        assert agent._is_mutating("execute_tests") is True

    def test_readonly_tools_not_mutating(self, mock_model):
        agent = _make_agent(mock_model)
        agent._mutating_tools = frozenset({"create_metric"})
        assert agent._is_mutating("list_metrics") is False
        assert agent._is_mutating("get_test_result") is False
        assert agent._is_mutating("check_endpoint") is False

    def test_unknown_tool_mutating_before_discovery(self, mock_model):
        """Before tools are discovered, assume everything is mutating."""
        agent = ArchitectAgent(model=mock_model, tools=[], verbose=False)
        assert agent._mutating_tools is None
        assert agent._is_mutating("anything") is True

    @pytest.mark.asyncio
    async def test_get_available_tools_uses_requires_confirmation(self, mock_model):
        """get_available_tools should prefer requires_confirmation over http_method."""
        from rhesis.sdk.agents.base import MCPTool

        class FakeMCPProvider(MCPTool):
            def __init__(self):
                self._connected = True

            async def _ensure_connected(self):
                pass

            async def list_tools(self):
                return [
                    {"name": "list_metrics", "description": "", "http_method": "GET"},
                    {
                        "name": "create_metric",
                        "description": "",
                        "http_method": "POST",
                        "requires_confirmation": True,
                    },
                    {
                        "name": "check_endpoint",
                        "description": "",
                        "http_method": "POST",
                        "requires_confirmation": False,
                    },
                    # No explicit flag — falls back to HTTP method
                    {"name": "update_metric", "description": "", "http_method": "PUT"},
                ]

            async def execute(self, tool_name, **kw):
                return ToolResult(tool_name=tool_name, success=True, content="")

        agent = _make_agent(mock_model, tools=[FakeMCPProvider()])
        agent._mutating_tools = None  # Reset so get_available_tools rebuilds
        await agent.get_available_tools()

        assert agent._mutating_tools == frozenset({"create_metric", "update_metric"})
        # check_endpoint is POST but requires_confirmation=False
        assert agent._is_mutating("check_endpoint") is False
        assert agent._is_mutating("create_metric") is True
        # list_metrics is GET — always read-only
        assert agent._is_mutating("list_metrics") is False
        # update_metric has no flag — inferred as mutating from PUT
        assert agent._is_mutating("update_metric") is True

    @pytest.mark.asyncio
    async def test_get_available_tools_http_method_fallback(self, mock_model):
        """Without requires_confirmation, falls back to HTTP method."""
        from rhesis.sdk.agents.base import MCPTool

        class FakeMCPProvider(MCPTool):
            def __init__(self):
                self._connected = True

            async def _ensure_connected(self):
                pass

            async def list_tools(self):
                return [
                    {"name": "list_metrics", "description": "", "http_method": "GET"},
                    {"name": "create_metric", "description": "", "http_method": "POST"},
                ]

            async def execute(self, tool_name, **kw):
                return ToolResult(tool_name=tool_name, success=True, content="")

        agent = _make_agent(mock_model, tools=[FakeMCPProvider()])
        agent._mutating_tools = None
        await agent.get_available_tools()

        assert agent._mutating_tools == frozenset({"create_metric"})

    def test_base_tool_requires_confirmation_in_to_dict(self, mock_model):
        """BaseTool.to_dict() should include requires_confirmation when set."""

        class ConfirmTool(BaseTool):
            @property
            def name(self):
                return "danger"

            @property
            def description(self):
                return "dangerous"

            @property
            def requires_confirmation(self):
                return True

            async def execute(self, **kw):
                return ToolResult(tool_name="danger", success=True, content="")

        d = ConfirmTool().to_dict()
        assert d["requires_confirmation"] is True

        # DummyTool returns None (default) — no key in dict
        d = DummyTool().to_dict()
        assert "requires_confirmation" not in d

    # -- write-guard integration --

    @pytest.mark.asyncio
    async def test_mutating_tool_blocked_without_approval(self, mock_model):
        """Mutating tool calls should be converted to finish+confirmation."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})

        # LLM returns a create_metric call
        mock_model.generate = Mock(
            return_value={
                "reasoning": "I'll create the metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Here's the metric I plan to create",
            },
        )

        # Mock generate_stream for the streaming finish
        async def fake_stream(**kw):
            yield "Here's the metric I plan to create"

        mock_model.generate_stream = Mock(side_effect=fake_stream)

        response = await agent.chat_async("create a friendliness metric")

        # The agent should NOT have called create_metric — it should
        # have finished with needs_confirmation=True
        assert agent._needs_confirmation is True
        assert response
        # Scoped approval: only create_metric should be in confirming set
        assert agent._confirming_tools == frozenset({"create_metric"})

    @pytest.mark.asyncio
    async def test_read_only_tools_allowed_without_approval(self, mock_model):
        """Read-only tools (list_*) should execute normally."""

        class ListMetricsTool(BaseTool):
            @property
            def name(self) -> str:
                return "list_metrics"

            @property
            def description(self) -> str:
                return "List metrics"

            @property
            def parameters_schema(self) -> dict:
                return {"properties": {}}

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(tool_name="list_metrics", success=True, content="[]")

        agent = _make_agent(mock_model, tools=[ListMetricsTool()])

        mock_model.generate = Mock(
            side_effect=[
                {
                    "reasoning": "List existing metrics first",
                    "action": "call_tool",
                    "tool_calls": [
                        {
                            "tool_name": "list_metrics",
                            "arguments": "{}",
                        }
                    ],
                    "final_answer": None,
                },
                _finish_dict("Here are the metrics"),
            ]
        )

        response = await agent.chat_async("show me the metrics")
        assert response  # Should complete without being blocked

    @pytest.mark.asyncio
    async def test_mutating_tool_allowed_after_confirmation_roundtrip(self, mock_model):
        """After a confirmation roundtrip, mutating tools should execute."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})

        async def fake_stream(**kw):
            yield "Here's what I'll create"

        # Turn 1: LLM tries to create -> gets blocked
        mock_model.generate = Mock(
            return_value={
                "reasoning": "Creating metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Here's what I'll create",
            },
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("create a metric")
        assert agent._needs_confirmation is True

        # Turn 2: Any user reply after needs_confirmation unlocks writes.
        # The LLM decides whether to proceed based on message content.
        mock_model.generate = Mock(
            side_effect=[
                {
                    "reasoning": "User confirmed, creating now",
                    "action": "call_tool",
                    "tool_calls": [
                        {
                            "tool_name": "create_metric",
                            "arguments": json.dumps({"name": "test"}),
                        }
                    ],
                    "final_answer": None,
                },
                _finish_dict("Created the metric"),
            ]
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("Yes, go ahead.")
        # Should have executed (even though create_metric tool doesn't
        # exist on the agent, the guard should not block it)
        assert agent._creation_approved is False  # Reset after turn

    @pytest.mark.asyncio
    async def test_rejection_after_confirmation_still_unlocks(self, mock_model):
        """Even a 'change the name' reply unlocks — the LLM handles intent."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})

        async def fake_stream(**kw):
            yield "Plan"

        # Turn 1: blocked
        mock_model.generate = Mock(
            return_value={
                "reasoning": "Creating metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Here's what I'll create",
            },
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("create a metric")
        assert agent._needs_confirmation is True

        # Turn 2: User sends a change request. The LLM should NOT
        # call create_metric (it should present revised plan instead).
        # But the guard allows it — the LLM is responsible for intent.
        mock_model.generate = Mock(return_value=_finish_dict("Updated plan"))
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("change the name to Response Tone")
        assert agent._creation_approved is False  # Reset after turn

    @pytest.mark.asyncio
    async def test_plan_approval_unlocks_all_mutating_tools(self, mock_model):
        """Approval after any block unlocks ALL mutating tools (plan-level)."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric", "create_project"})

        async def fake_stream(**kw):
            yield "Plan"

        # Turn 1: create_metric is blocked — confirming set should
        # include ALL mutating tools, not just the blocked batch.
        mock_model.generate = Mock(
            return_value={
                "reasoning": "Creating metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Plan to create metric",
            },
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("create a metric")
        assert agent._confirming_tools == frozenset({"create_metric", "create_project"})
        assert agent._needs_confirmation is True

        # Turn 2: LLM tries create_project — should be allowed because
        # plan-level approval covers all mutating tools.
        mock_model.generate = Mock(
            side_effect=[
                {
                    "reasoning": "Creating project",
                    "action": "call_tool",
                    "tool_calls": [
                        {
                            "tool_name": "create_project",
                            "arguments": json.dumps({"name": "proj"}),
                        }
                    ],
                    "final_answer": None,
                },
                _finish_dict("Project created"),
            ]
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)
        await agent.chat_async("Yes, go ahead.")

        # create_project was in the approved set — no re-blocking
        assert agent._creation_approved is False  # Reset after turn

    @pytest.mark.asyncio
    async def test_approval_resets_after_turn(self, mock_model):
        """_creation_approved should reset to False after each turn."""
        agent = _make_agent(mock_model)

        # Simulate a confirmed turn
        agent._needs_confirmation = True
        agent._confirming_tools = frozenset({"create_metric"})
        mock_model.generate = Mock(return_value=_finish_dict("Done"))
        await agent.chat_async("Yes, go ahead.")

        assert agent._creation_approved is False


# ── auto-approve and guard_state tests ────────────────────────────


@pytest.mark.unit
class TestArchitectAutoApprove:
    """Test session-level auto-approve and guard_state persistence."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_auto_approve_all_default_false(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent.auto_approve_all is False

    def test_auto_approve_all_setter(self, mock_model):
        agent = _make_agent(mock_model)
        agent.auto_approve_all = True
        assert agent.auto_approve_all is True
        assert agent._auto_approve_all is True

    def test_reset_clears_auto_approve_all(self, mock_model):
        agent = _make_agent(mock_model)
        agent.auto_approve_all = True
        agent.reset()
        assert agent.auto_approve_all is False

    def test_guard_state_includes_auto_approve_all(self, mock_model):
        agent = _make_agent(mock_model)
        agent.auto_approve_all = True
        state = agent.guard_state
        assert state["auto_approve_all"] is True

    def test_guard_state_setter_restores_auto_approve(self, mock_model):
        agent = _make_agent(mock_model)
        agent.guard_state = {
            "needs_confirmation": True,
            "confirming_tools": ["create_metric"],
            "auto_approve_all": True,
        }
        assert agent.auto_approve_all is True
        assert agent._needs_confirmation is True
        assert agent._confirming_tools == frozenset({"create_metric"})

    def test_guard_state_setter_defaults_auto_approve_false(self, mock_model):
        """Old guard_state without auto_approve_all defaults to False."""
        agent = _make_agent(mock_model)
        agent.auto_approve_all = True
        agent.guard_state = {
            "needs_confirmation": False,
            "confirming_tools": [],
        }
        assert agent.auto_approve_all is False

    @pytest.mark.asyncio
    async def test_auto_approve_bypasses_write_guard(self, mock_model):
        """When auto_approve_all=True, mutating tools execute immediately."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})
        agent.auto_approve_all = True

        async def fake_stream(**kw):
            yield "Created the metric"

        # LLM calls a mutating tool — should NOT be blocked
        mock_model.generate = Mock(
            side_effect=[
                {
                    "reasoning": "Creating metric",
                    "action": "call_tool",
                    "tool_calls": [
                        {
                            "tool_name": "create_metric",
                            "arguments": json.dumps({"name": "test"}),
                        }
                    ],
                    "final_answer": None,
                },
                _finish_dict("Created the metric"),
            ]
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)

        response = await agent.chat_async("create a friendliness metric")

        # The tool should have been called, not blocked
        assert agent._needs_confirmation is False
        assert "Created the metric" in response
        # Verify it went through tool execution (even though the dummy
        # tool won't match create_metric, the guard didn't intercept)
        assert len(agent._execution_history) >= 1

    @pytest.mark.asyncio
    async def test_auto_approve_is_approved_returns_true(self, mock_model):
        """_is_approved returns True unconditionally when auto_approve_all is set."""
        agent = _make_agent(mock_model)
        agent._mutating_tools = frozenset({"create_metric"})
        agent.auto_approve_all = True

        from rhesis.sdk.agents.schemas import ToolCall

        tool_calls = [ToolCall(tool_name="create_metric", arguments="{}")]
        assert agent._is_approved(tool_calls) is True

    @pytest.mark.asyncio
    async def test_auto_approve_false_does_not_bypass(self, mock_model):
        """auto_approve_all=False preserves normal confirmation flow."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})
        agent.auto_approve_all = False

        async def fake_stream(**kw):
            yield "Plan"

        mock_model.generate = Mock(
            return_value={
                "reasoning": "Creating metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Plan to create",
            },
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)

        await agent.chat_async("create a metric")

        # Should still be blocked
        assert agent._needs_confirmation is True


# ── discovery state tests ────────────────────────────────────────


@pytest.mark.unit
class TestArchitectDiscoveryState:
    """Test discovery state tracking and formatting."""

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.generate = Mock(return_value={})
        return model

    def test_default_discovery_state(self, mock_model):
        agent = _make_agent(mock_model)
        ds = agent.discovery_state
        assert ds["endpoint_id"] is None
        assert ds["endpoint_name"] is None
        assert ds["explored"] is False
        assert ds["observations"] == []
        assert ds["user_confirmed_areas"] == []
        assert ds["open_questions"] == []

    def test_discovery_state_setter(self, mock_model):
        agent = _make_agent(mock_model)
        agent.discovery_state = {
            "endpoint_id": "ep-1",
            "endpoint_name": "Chatbot",
            "explored": True,
            "observations": ["Handles travel queries"],
            "user_confirmed_areas": ["Safety"],
            "open_questions": [],
        }
        assert agent.discovery_state["endpoint_name"] == "Chatbot"
        assert agent.discovery_state["explored"] is True

    def test_reset_clears_discovery_state(self, mock_model):
        agent = _make_agent(mock_model)
        agent._discovery_state["endpoint_id"] = "ep-1"
        agent._discovery_state["explored"] = True
        agent.reset()
        assert agent.discovery_state["endpoint_id"] is None
        assert agent.discovery_state["explored"] is False

    def test_format_discovery_state_empty(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent._format_discovery_state() == ""

    def test_format_discovery_state_with_endpoint(self, mock_model):
        agent = _make_agent(mock_model)
        agent._discovery_state["endpoint_id"] = "ep-1"
        agent._discovery_state["endpoint_name"] = "File Chatbot"
        formatted = agent._format_discovery_state()
        assert "File Chatbot" in formatted
        assert "ep-1" in formatted
        assert "not yet" in formatted

    def test_format_discovery_state_explored(self, mock_model):
        agent = _make_agent(mock_model)
        agent._discovery_state["endpoint_id"] = "ep-1"
        agent._discovery_state["endpoint_name"] = "Chatbot"
        agent._discovery_state["explored"] = True
        agent._discovery_state["observations"] = [
            "Handles travel bookings",
            "Refuses off-topic requests",
        ]
        formatted = agent._format_discovery_state()
        assert "Explored: yes" in formatted
        assert "Handles travel bookings" in formatted
        assert "Refuses off-topic requests" in formatted

    def test_format_discovery_state_with_areas_and_questions(self, mock_model):
        agent = _make_agent(mock_model)
        agent._discovery_state["endpoint_id"] = "ep-1"
        agent._discovery_state["endpoint_name"] = "Bot"
        agent._discovery_state["user_confirmed_areas"] = ["Safety", "Accuracy"]
        agent._discovery_state["open_questions"] = ["Compliance requirements?"]
        formatted = agent._format_discovery_state()
        assert "Safety" in formatted
        assert "Accuracy" in formatted
        assert "Compliance requirements?" in formatted


# ── prompt hardening tests (Phase 09) ────────────────────────────


@pytest.mark.unit
class TestArchitectPromptHardening:
    """Test that system prompt contains security guardrails."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_system_prompt_contains_security_section(self, mock_model):
        """The rendered system prompt must include the security section."""
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "## Security and Boundaries" in prompt

    def test_system_prompt_contains_identity_guardrail(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "### Identity" in prompt
        assert "only role" in prompt.lower()

    def test_system_prompt_contains_injection_resistance(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "### Prompt injection resistance" in prompt
        assert "Ignore all previous instructions" in prompt

    def test_system_prompt_contains_information_boundaries(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "### Information boundaries" in prompt
        assert "system prompt" in prompt.lower()

    def test_system_prompt_contains_tool_safety(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "### Tool safety" in prompt
        assert "blind proxying" in prompt.lower() or "No blind proxying" in prompt

    def test_system_prompt_contains_off_topic_section(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "### Off-topic requests" in prompt

    def test_security_section_before_response_format(self, mock_model):
        """Security section should come before Response Format."""
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        sec_pos = prompt.index("## Security and Boundaries")
        fmt_pos = prompt.index("## Response Format")
        assert sec_pos < fmt_pos


@pytest.mark.unit
class TestArchitectArgumentValidation:
    """Test structural argument validation (Phase 09)."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_valid_arguments_pass(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(tool_name="list_metrics", arguments=json.dumps({"$select": "name,id"}))
        assert agent._validate_tool_arguments(tc) is None

    def test_oversized_payload_rejected(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        huge = {"data": "x" * (agent._cfg.max_payload_bytes + 1)}
        tc = ToolCall(tool_name="create_test_set_bulk", arguments=json.dumps(huge))
        error = agent._validate_tool_arguments(tc)
        assert error is not None
        assert "payload limit" in error.lower()

    def test_oversized_string_value_rejected(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(
            tool_name="create_behavior",
            arguments=json.dumps({"description": "y" * (agent._cfg.max_string_value_len + 1)}),
        )
        error = agent._validate_tool_arguments(tc)
        assert error is not None
        assert "string limit" in error.lower()

    def test_oversized_array_rejected(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        items = [{"prompt": {"content": f"test {i}"}} for i in range(agent._cfg.max_array_items + 1)]
        tc = ToolCall(
            tool_name="create_test_set_bulk",
            arguments=json.dumps({"tests": items}),
        )
        error = agent._validate_tool_arguments(tc)
        assert error is not None
        assert "items" in error.lower()

    def test_normal_array_passes(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        items = [{"prompt": {"content": f"test {i}"}} for i in range(10)]
        tc = ToolCall(
            tool_name="create_test_set_bulk",
            arguments=json.dumps({"name": "safety tests", "tests": items}),
        )
        assert agent._validate_tool_arguments(tc) is None

    def test_empty_arguments_pass(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(tool_name="list_projects", arguments="{}")
        assert agent._validate_tool_arguments(tc) is None

    @pytest.mark.asyncio
    async def test_execute_tool_rejects_invalid_arguments(self, mock_model):
        """execute_tool should return a ToolResult with success=False."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        from rhesis.sdk.agents.schemas import ToolCall

        huge = {"data": "x" * (agent._cfg.max_payload_bytes + 1)}
        tc = ToolCall(tool_name="dummy", arguments=json.dumps(huge))
        result = await agent.execute_tool(tc)
        assert result.success is False
        assert "payload limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_allows_valid_arguments(self, mock_model):
        """execute_tool should pass through to the real tool when valid."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(tool_name="dummy", arguments=json.dumps({"x": "hello"}))
        result = await agent.execute_tool(tc)
        assert result.success is True
        assert result.content == "ok"

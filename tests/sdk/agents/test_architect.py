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
    model.a_generate = AsyncMock(return_value={})

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
        model.a_generate = AsyncMock(return_value={})
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
        model.a_generate = AsyncMock(return_value={})
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
        mock_model.a_generate.return_value = _finish_dict("hello")

        response = await agent.chat_async("hi")
        assert response == "hello"

    @pytest.mark.asyncio
    async def test_max_iterations_stops_loop(self, mock_model):
        agent = _make_agent(mock_model, max_iterations=2)
        mock_model.a_generate.return_value = _tool_dict()

        response = await agent.chat_async("hi")
        assert "maximum number of internal iterations" in response
        assert mock_model.a_generate.call_count == 2

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
        mock_model.a_generate.return_value = _tool_dict()

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
        mock_model.a_generate.return_value = _tool_dict()

        response = await agent.chat_async("go")
        assert "run out of time" in response

    @pytest.mark.asyncio
    async def test_llm_error_returns_error_message(self, mock_model):
        agent = _make_agent(mock_model)
        mock_model.a_generate.side_effect = ValueError("bad json")

        response = await agent.chat_async("hi")
        # On LLM error, _run_loop returns the empty string from
        # the finish step's content (error step)
        assert response is not None


@pytest.mark.unit
class TestArchitectAgentLifecycleEvents:
    """``chat_async`` must emit ``on_agent_end`` so handlers that
    open spans / resources in ``on_agent_start`` (notably
    ``TracingHandler``'s ``function.mcp_agent_run`` span) can close
    them.  Skipping it leaks the OTel context token and leaves
    iteration spans orphaned at the trace root.
    """

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        return model

    @pytest.mark.asyncio
    async def test_chat_async_emits_agent_end_on_success(self, mock_model):
        from rhesis.sdk.agents.events import AgentEventHandler

        handler = Mock(spec=AgentEventHandler)
        handler.on_agent_start = AsyncMock()
        handler.on_agent_end = AsyncMock()

        agent = _make_agent(mock_model)
        agent._event_handlers = [handler]
        mock_model.a_generate.return_value = _finish_dict("hello")

        await agent.chat_async("hi")

        handler.on_agent_start.assert_awaited_once()
        handler.on_agent_end.assert_awaited_once()
        result_kwarg = handler.on_agent_end.await_args.kwargs["result"]
        assert result_kwarg.success is True
        assert result_kwarg.final_answer == "hello"

    @pytest.mark.asyncio
    async def test_chat_async_emits_agent_end_on_exception(self, mock_model):
        from rhesis.sdk.agents.events import AgentEventHandler

        handler = Mock(spec=AgentEventHandler)
        handler.on_agent_start = AsyncMock()
        handler.on_agent_end = AsyncMock()

        agent = _make_agent(mock_model)
        agent._event_handlers = [handler]

        async def _boom(*_a, **_k):
            raise RuntimeError("kaboom")

        agent._run_loop = _boom  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="kaboom"):
            await agent.chat_async("hi")

        handler.on_agent_end.assert_awaited_once()
        result_kwarg = handler.on_agent_end.await_args.kwargs["result"]
        assert result_kwarg.success is False
        assert "kaboom" in (result_kwarg.error or "")


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

        mock_model.a_generate.side_effect = [
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

        mock_model.a_generate.side_effect = [
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
        model.a_generate = AsyncMock(return_value={})
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
        mock_model.a_generate = AsyncMock(
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

        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(return_value=_finish_dict("Updated plan"))
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
        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(
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
        mock_model.a_generate = AsyncMock(return_value=_finish_dict("Done"))
        await agent.chat_async("Yes, go ahead.")

        assert agent._creation_approved is False

    @pytest.mark.asyncio
    async def test_llm_self_reported_needs_confirmation_is_ignored(self, mock_model):
        """LLM-set needs_confirmation=True must NOT trigger Accept/Change UI.

        ``needs_confirmation`` on the response is computed from runtime
        state (specifically ``_confirming_tools``, populated when a tool
        flagged ``requires_confirmation: true`` in mcp_tools.yaml is
        called). A finish action that the LLM emits with
        ``needs_confirmation=True`` but no actual blocked tool — for
        example after asking "Quick or Comprehensive exploration?" —
        must resolve to False, otherwise the UI surfaces misleading
        Accept/Change buttons on open-ended questions.
        """
        agent = _make_agent(mock_model)
        agent._mutating_tools = frozenset({"create_metric"})
        assert agent._confirming_tools == frozenset()

        async def fake_stream(**kw):
            yield "Quick or comprehensive?"

        mock_model.a_generate = AsyncMock(
            return_value={
                "reasoning": "Asking the user how thorough to be.",
                "action": "finish",
                "tool_calls": [],
                "final_answer": "Would you prefer Quick or Comprehensive?",
                "needs_confirmation": True,
            }
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)

        await agent.chat_async("design a test suite")

        assert agent._needs_confirmation is False
        assert agent._confirming_tools == frozenset()

    @pytest.mark.asyncio
    async def test_finish_after_approved_tool_does_not_re_surface_confirmation(
        self, mock_model
    ):
        """Auto-resumed summaries must not inherit a stale confirmation flag.

        Reproduces the bug where the Accept/Change UI re-appeared on
        the post-exploration summary turn even though no tool had
        been blocked in that turn. The flow is:

          Turn 1: LLM tries explore_endpoint -> blocked
                  -> _confirming_tools populated, _needs_confirmation=True
          Turn 2: user approves, tool runs, await_task pauses turn
                  -> _creation_approved reset to False at end of turn
                  -> _confirming_tools STILL populated (long-lived scope)
          Turn 3: auto-resumed [TASK_COMPLETED] -> LLM finishes with
                  a plain summary, no tool call.

        On Turn 3 the runtime must report _needs_confirmation=False.
        Driving this off ``_confirming_tools`` (the previous
        implementation) wrongly returned True because that set
        survives across turns. The correct signal is the per-turn
        ``_blocked_this_turn`` flag.
        """
        agent = _make_agent(mock_model)
        # Simulate the residual state left behind by an earlier
        # approved confirmation roundtrip: scope still set, no
        # active block this turn, no fresh approval.
        agent._mutating_tools = frozenset({"explore_endpoint", "create_metric"})
        agent._confirming_tools = frozenset({"explore_endpoint", "create_metric"})
        agent._creation_approved = False
        assert agent._blocked_this_turn is False

        async def fake_stream(**kw):
            yield "Here's what I learned about your endpoint."

        mock_model.a_generate = AsyncMock(
            return_value={
                "reasoning": "Summarising the exploration findings.",
                "action": "finish",
                "tool_calls": [],
                "final_answer": "Here's what I learned about your endpoint.",
            }
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)

        await agent.chat_async("[TASK_COMPLETED] explore_endpoint")

        assert agent._needs_confirmation is False
        assert agent._blocked_this_turn is False

    @pytest.mark.asyncio
    async def test_blocked_tool_sets_needs_confirmation_without_llm_flag(
        self, mock_model
    ):
        """Runtime derivation works even when the LLM omits the flag.

        When the LLM tries to call a mutating tool, ``_handle_tool_calls``
        populates ``_confirming_tools`` and constructs a finish action
        WITHOUT setting ``needs_confirmation``. The downstream
        ``_handle_finish_action`` must still resolve to True based on
        ``_confirming_tools`` alone.
        """
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool])
        agent._mutating_tools = frozenset({"create_metric"})

        async def fake_stream(**kw):
            yield "Here's the metric I plan to create"

        mock_model.a_generate = AsyncMock(
            return_value={
                "reasoning": "Creating metric",
                "action": "call_tool",
                "tool_calls": [
                    {
                        "tool_name": "create_metric",
                        "arguments": json.dumps({"name": "test"}),
                    }
                ],
                "final_answer": "Here's the metric I plan to create",
                "needs_confirmation": False,
            }
        )
        mock_model.generate_stream = Mock(side_effect=fake_stream)

        await agent.chat_async("create a metric")

        assert agent._needs_confirmation is True
        assert agent._confirming_tools == frozenset({"create_metric"})


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
        mock_model.a_generate = AsyncMock(
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

        mock_model.a_generate = AsyncMock(
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
        model.a_generate = AsyncMock(return_value={})
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
class TestArchitectNameResolutionGuidance:
    """Verify the prompt teaches a typo-tolerant name-resolution ladder.

    The agent must walk through progressively broader filters when
    resolving an entity name — exact match, whole-string contains,
    token-OR contains, and finally a suggestion fallback over an
    unfiltered page. Without the token-OR step, single-character
    typos like "rosalinf" instead of "rosalind" dead-end with
    "no match found" because OData ``contains`` is a substring
    operator, not a fuzzy operator.
    """

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_resolution_section_present(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "## Resolving Entities by Name" in prompt

    def test_exact_match_tier_documented(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "Exact match" in prompt
        assert "tolower(name) eq" in prompt

    def test_whole_string_contains_tier_documented(self, mock_model):
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        assert "Whole-string contains" in prompt
        assert "contains(tolower(name)" in prompt

    def test_token_or_typo_fallback_documented(self, mock_model):
        """The token-OR fallback is the typo-tolerance mechanism."""
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt.lower()
        assert "token-or contains" in prompt
        assert "typo" in prompt
        # The example must illustrate the failure mode (typo'd name
        # matched via clean tokens) so the LLM can pattern-match
        # on real cases.
        assert "rosalinf" in prompt
        assert "rosalind" in prompt

    def test_suggestion_fallback_documented(self, mock_model):
        """When all filters fail, the agent should suggest candidates."""
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt.lower()
        assert "suggestion fallback" in prompt
        assert "did you mean" in prompt

    def test_resolution_tiers_appear_in_order(self, mock_model):
        """Tiers must be listed in escalation order so the LLM walks them top-down."""
        agent = _make_agent(mock_model)
        prompt = agent.system_prompt
        exact_pos = prompt.index("Exact match")
        whole_pos = prompt.index("Whole-string contains")
        token_pos = prompt.index("Token-OR contains")
        suggest_pos = prompt.index("Suggestion fallback")
        assert exact_pos < whole_pos < token_pos < suggest_pos


@pytest.mark.unit
class TestArchitectSkillIncludes:
    """Verify Telemachus loads shared skill references (lazy per phase)."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_workflow_menu_in_prompt(self, mock_model):
        prompt = _make_agent(mock_model).system_prompt
        assert "Quick exploration" in prompt
        assert "Build a test foundation from your PRD" in prompt

    def test_exploration_not_in_system_prompt(self, mock_model):
        """Heavy phase content loads per iteration, not in the fixed system prompt."""
        system = _make_agent(mock_model).system_prompt
        assert "domain_probing" not in system.lower()
        assert "save_plan is strictly validated" not in system

    def test_discovery_phase_in_iteration_prompt(self, mock_model):
        from rhesis.sdk.agents.architect.workflow import WorkflowPath

        agent = _make_agent(mock_model)
        agent._workflow_path = WorkflowPath.EXPLORE
        iteration = agent._build_prompt("explore my endpoint", [])
        assert "domain_probing" in iteration.lower() or "explore_endpoint" in iteration

    def test_planning_phase_in_iteration_prompt(self, mock_model):
        from rhesis.sdk.agents.architect.workflow import WorkflowPath
        from rhesis.sdk.agents.constants import AgentMode

        agent = _make_agent(mock_model)
        agent._mode = AgentMode.PLANNING
        agent._workflow_path = WorkflowPath.PRD
        iteration = agent._build_prompt("plan the suite", [])
        assert "save_plan is strictly validated" in iteration
        assert "PRD" in iteration or "acceptance criteria" in iteration.lower()

    def test_rendered_system_prompt_smaller_than_eager_load(self, mock_model):
        """Fixed prompt stays lean vs old ~1400-line eager load.

        Always-on guidelines and OData patterns are hoisted into the system
        prompt (~530 lines); phase-specific content still loads per iteration.
        """
        agent = _make_agent(mock_model)
        lines = agent.system_prompt.splitlines()
        assert len(lines) < 600, f"system prompt still {len(lines)} lines"
        assert len(lines) < 900, "should remain well under the old eager-load size"


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

        max_items = agent._cfg.max_array_items
        items = [{"prompt": {"content": f"test {i}"}} for i in range(max_items + 1)]
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


# ── await_task tests ─────────────────────────────────────────────


@pytest.mark.unit
class TestArchitectAwaitTask:
    """Test the await_task internal tool and iteration override."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @pytest.mark.asyncio
    async def test_await_task_stores_pending_tasks(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(
            tool_name="await_task",
            arguments=json.dumps({
                "task_ids": ["tid-1", "tid-2"],
                "message": "Generating tests...",
            }),
        )
        result = await agent.execute_tool(tc)
        assert result.success is True
        assert len(agent.pending_tasks) == 2
        assert agent.pending_tasks[0]["task_id"] == "tid-1"
        assert agent.pending_tasks[1]["task_id"] == "tid-2"
        assert agent._awaiting_task is True
        assert agent._await_message == "Generating tests..."

    @pytest.mark.asyncio
    async def test_await_task_rejects_empty_task_ids(self, mock_model):
        agent = _make_agent(mock_model)
        from rhesis.sdk.agents.schemas import ToolCall

        tc = ToolCall(
            tool_name="await_task",
            arguments=json.dumps({
                "task_ids": [],
                "message": "Waiting...",
            }),
        )
        result = await agent.execute_tool(tc)
        assert result.success is False
        assert "required" in result.error.lower()
        assert agent._awaiting_task is False

    @pytest.mark.asyncio
    async def test_await_task_forces_turn_finish(self, mock_model):
        """When await_task is called, the agent's turn should end."""
        agent = _make_agent(mock_model, max_iterations=5)

        mock_model.a_generate.side_effect = [
            _tool_dict("await_task", {
                "task_ids": ["tid-1"],
                "message": "Generating tests...",
            }),
            # The agent should NOT reach a second iteration
            _finish_dict("should not reach here"),
        ]

        response = await agent.chat_async("go ahead")
        assert "Generating tests..." in response
        assert len(agent.pending_tasks) == 1
        assert mock_model.a_generate.call_count == 1
        assert agent.needs_confirmation is False

    @pytest.mark.asyncio
    async def test_pending_tasks_cleared_on_new_turn(self, mock_model):
        """pending_tasks should be cleared at the start of each turn."""
        agent = _make_agent(mock_model)
        agent._pending_tasks = [{"task_id": "old-task"}]
        agent._awaiting_task = True

        mock_model.a_generate.side_effect = [_finish_dict("hello")]

        await agent.chat_async("new message")
        assert agent.pending_tasks == []
        assert agent._awaiting_task is False

    @pytest.mark.asyncio
    async def test_pending_tasks_cleared_on_reset(self, mock_model):
        agent = _make_agent(mock_model)
        agent._pending_tasks = [{"task_id": "task-1"}]
        agent._awaiting_task = True
        agent._await_message = "waiting"

        agent.reset()
        assert agent.pending_tasks == []
        assert agent._awaiting_task is False
        assert agent._await_message == ""

    @pytest.mark.asyncio
    async def test_await_task_tool_in_available_tools(self, mock_model):
        agent = _make_agent(mock_model)
        tools = await agent.get_available_tools()
        tool_names = [t["name"] for t in tools]
        assert "await_task" in tool_names

    @pytest.mark.asyncio
    async def test_await_task_after_other_tools(self, mock_model):
        """Agent can call tools then await_task in the same turn."""
        tool = DummyTool()
        agent = _make_agent(mock_model, tools=[tool], max_iterations=5)

        mock_model.a_generate.side_effect = [
            _tool_dict("dummy", {"x": "work"}),
            _tool_dict("await_task", {
                "task_ids": ["tid-1"],
                "message": "Now waiting...",
            }),
        ]

        response = await agent.chat_async("do work then wait")
        assert "Now waiting..." in response
        assert len(agent.pending_tasks) == 1
        assert mock_model.a_generate.call_count == 2


# ── deferred test set completion tests ───────────────────────────


@pytest.mark.unit
class TestArchitectDeferredTestSetCompletion:
    """Test that generate_test_set does not immediately mark test sets
    as completed, and that [TASK_COMPLETED] messages do."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @pytest.mark.asyncio
    async def test_generate_test_set_does_not_mark_completed(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, TestSetSpec

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[TestSetSpec(name="Safety Tests", description="d")],
            metrics=[],
        )

        mock_model.a_generate.side_effect = [
            _tool_dict("generate_test_set", {"name": "Safety Tests"}),
            _tool_dict("await_task", {
                "task_ids": ["tid-1"],
                "message": "Generating...",
            }),
        ]

        await agent.chat_async("create tests")
        assert not agent._plan.test_sets[0].completed

    @pytest.mark.asyncio
    async def test_task_completed_message_marks_test_sets(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, TestSetSpec

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[
                TestSetSpec(name="Safety Tests", description="d"),
                TestSetSpec(name="Accuracy Tests", description="d"),
            ],
            metrics=[],
        )

        msg = (
            "[TASK_COMPLETED] The background tasks you were waiting "
            "for have finished. Here are the results:\n"
            "- Test set 'Safety Tests' generated successfully "
            "(5 tests). test_set_id=ts-1\n"
            "- Test set 'Accuracy Tests' generated successfully "
            "(10 tests). test_set_id=ts-2\n"
            "Please continue with the next steps in the plan."
        )

        mock_model.a_generate.side_effect = [_finish_dict("done")]

        await agent.chat_async(msg)
        assert agent._plan.test_sets[0].completed is True
        assert agent._plan.test_sets[1].completed is True

    @pytest.mark.asyncio
    async def test_task_completed_partial_match(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, TestSetSpec

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[
                TestSetSpec(name="Safety Tests", description="d"),
                TestSetSpec(name="Other Tests", description="d"),
            ],
            metrics=[],
        )

        msg = (
            "[TASK_COMPLETED] Results:\n"
            "- Test set 'Safety Tests' generated successfully "
            "(5 tests). test_set_id=ts-1\n"
        )

        mock_model.a_generate.side_effect = [_finish_dict("done")]

        await agent.chat_async(msg)
        assert agent._plan.test_sets[0].completed is True
        assert agent._plan.test_sets[1].completed is False


# ── plan constraints tests ───────────────────────────────────────


@pytest.mark.unit
class TestArchitectPlanConstraints:
    """Test structural guards that prevent plan violations."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_rejects_create_project_without_plan_project(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[],
            metrics=[],
        )
        tc = ToolCall(
            tool_name="create_project",
            arguments=json.dumps({"name": "Rogue Project"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "does not include a project" in error

    def test_allows_create_project_with_plan_project(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, ProjectSpec
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            project=ProjectSpec(name="Real Project", description="A test project"),
            behaviors=[],
            test_sets=[],
            metrics=[],
        )
        tc = ToolCall(
            tool_name="create_project",
            arguments=json.dumps({"name": "Real Project"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is None

    def test_rejects_metric_name_mismatch(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[],
            metrics=[MetricSpec(name="Factual Accuracy", description="Checks facts")],
        )
        tc = ToolCall(
            tool_name="create_metric",
            arguments=json.dumps({"name": "Conversation Coherence"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "does not match" in error
        assert "Factual Accuracy" in error

    def test_allows_matching_metric_name(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[],
            metrics=[MetricSpec(name="Factual Accuracy", description="Checks facts")],
        )
        tc = ToolCall(
            tool_name="create_metric",
            arguments=json.dumps({"name": "factual accuracy"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is None

    def test_no_constraints_without_plan(self, mock_model):
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        tc = ToolCall(
            tool_name="create_project",
            arguments=json.dumps({"name": "anything"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is None

    def test_rejects_already_completed_metric(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[],
            metrics=[MetricSpec(
                name="Factual Accuracy",
                description="d",
                completed=True,
            )],
        )
        tc = ToolCall(
            tool_name="create_metric",
            arguments=json.dumps({"name": "Factual Accuracy"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "already completed" in error

    def test_rejects_already_completed_behavior(self, mock_model):
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[BehaviorSpec(
                name="Safety",
                description="d",
                completed=True,
            )],
            test_sets=[],
            metrics=[],
        )
        tc = ToolCall(
            tool_name="create_behavior",
            arguments=json.dumps({"name": "Safety"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "already completed" in error

    def test_allows_incomplete_item(self, mock_model):
        from rhesis.sdk.agents.architect.plan import ArchitectPlan, MetricSpec
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[],
            metrics=[MetricSpec(
                name="Factual Accuracy",
                description="d",
                completed=False,
            )],
        )
        tc = ToolCall(
            tool_name="create_metric",
            arguments=json.dumps({"name": "Factual Accuracy"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is None

    def test_blocks_test_set_when_behaviors_incomplete(self, mock_model):
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            TestSetSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[BehaviorSpec(
                name="Safety",
                description="d",
                completed=False,
            )],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[],
        )
        tc = ToolCall(
            tool_name="generate_test_set",
            arguments=json.dumps({"name": "Tests"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "behavior 'Safety'" in error

    def test_blocks_test_set_when_metrics_incomplete(self, mock_model):
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            MetricSpec,
            TestSetSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[MetricSpec(
                name="Accuracy",
                description="d",
                completed=False,
            )],
        )
        tc = ToolCall(
            tool_name="generate_test_set",
            arguments=json.dumps({"name": "Tests"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "metric 'Accuracy'" in error

    def test_blocks_test_set_when_mappings_incomplete(self, mock_model):
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            MappingSpec,
            TestSetSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[],
            behavior_metric_mappings=[MappingSpec(
                behavior="Safety",
                metrics=["Accuracy"],
            )],
        )
        tc = ToolCall(
            tool_name="generate_test_set",
            arguments=json.dumps({"name": "Tests"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is not None
        assert "mapping" in error

    def test_allows_test_set_when_all_prereqs_done(self, mock_model):
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._plan = ArchitectPlan(
            behaviors=[BehaviorSpec(
                name="Safety", description="d", completed=True,
            )],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[MetricSpec(
                name="Accuracy", description="d", completed=True,
            )],
            behavior_metric_mappings=[MappingSpec(
                behavior="Safety",
                metrics=["Accuracy"],
                completed=True,
            )],
        )
        tc = ToolCall(
            tool_name="generate_test_set",
            arguments=json.dumps({"name": "Tests"}),
        )
        error = agent._check_plan_constraints(tc)
        assert error is None


# ── ID-to-name collection tests ──────────────────────────────────


@pytest.mark.unit
class TestArchitectIdNameCollection:
    """Test ID-to-name resolution from tool results."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    def test_collects_from_single_object(self, mock_model):
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="create_behavior",
            success=True,
            content=json.dumps({"id": "uuid-1", "name": "Safety"}),
        )
        agent._collect_id_names(result)
        assert agent._id_to_name["uuid-1"] == "Safety"

    def test_collects_from_list(self, mock_model):
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="list_behaviors",
            success=True,
            content=json.dumps([
                {"id": "uuid-1", "name": "Safety"},
                {"id": "uuid-2", "name": "Accuracy"},
            ]),
        )
        agent._collect_id_names(result)
        assert agent._id_to_name["uuid-1"] == "Safety"
        assert agent._id_to_name["uuid-2"] == "Accuracy"

    def test_collects_from_odata_value_wrapper(self, mock_model):
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="list_metrics",
            success=True,
            content=json.dumps({
                "value": [
                    {"id": "uuid-3", "name": "Relevance"},
                ]
            }),
        )
        agent._collect_id_names(result)
        assert agent._id_to_name["uuid-3"] == "Relevance"

    def test_collects_from_mcp_results_envelope(self, mock_model):
        """MCP server wraps paginated list responses in {results, _pagination}.

        Without this support the architect drops every ID returned by
        list_behaviors / list_metrics, breaking add_behavior_to_metric
        progress tracking downstream.
        """
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="list_behaviors",
            success=True,
            content=json.dumps({
                "results": [
                    {"id": "uuid-1", "name": "Safety"},
                    {"id": "uuid-2", "name": "Accuracy"},
                ],
                "_pagination": {"returned": 2, "has_more": False},
            }),
        )
        agent._collect_id_names(result)
        assert agent._id_to_name["uuid-1"] == "Safety"
        assert agent._id_to_name["uuid-2"] == "Accuracy"

    def test_skips_failed_results(self, mock_model):
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="create_behavior",
            success=False,
            error="validation error",
        )
        agent._collect_id_names(result)
        assert len(agent._id_to_name) == 0

    def test_skips_malformed_json(self, mock_model):
        agent = _make_agent(mock_model)
        result = ToolResult(
            tool_name="create_behavior",
            success=True,
            content="not json",
        )
        agent._collect_id_names(result)
        assert len(agent._id_to_name) == 0

    def test_id_to_name_cleared_on_reset(self, mock_model):
        agent = _make_agent(mock_model)
        agent._id_to_name["uuid-1"] = "test"
        agent.reset()
        assert len(agent._id_to_name) == 0


# ── Compact list rendering for history ───────────────────────────


@pytest.mark.unit
class TestArchitectCompactListRendering:
    """The iteration prompt truncates each tool result at a fixed char
    budget. A raw 20-item list_metrics JSON easily exceeds that budget,
    silently hiding items from the LLM and making it think entities
    don't exist. The compact renderer must render every item on the
    page in much less space, preserving id, name, short description,
    and pagination state.
    """

    @staticmethod
    def _metric(idx: int, *, desc_chars: int = 80) -> dict:
        return {
            "id": f"00000000-0000-0000-0000-{idx:012d}",
            "name": f"Metric {idx}",
            "description": "x" * desc_chars,
            "score_type": "binary",
            "metric_scope": "endpoint",
        }

    def test_returns_none_for_non_list_payload(self):
        """Single-object responses fall back to plain truncation."""
        out = ArchitectAgent._compact_list_result_for_history(
            json.dumps({"id": "u-1", "name": "Solo"})
        )
        assert out is None

    def test_returns_none_for_invalid_json(self):
        out = ArchitectAgent._compact_list_result_for_history("not json")
        assert out is None

    def test_returns_none_for_empty_string(self):
        out = ArchitectAgent._compact_list_result_for_history("")
        assert out is None

    def test_renders_bare_list(self):
        items = [
            {"id": "u-1", "name": "Alpha", "description": "first"},
            {"id": "u-2", "name": "Beta", "description": "second"},
        ]
        out = ArchitectAgent._compact_list_result_for_history(json.dumps(items))
        assert out is not None
        assert "Alpha" in out and "u-1" in out
        assert "Beta" in out and "u-2" in out
        assert "List response: 2 item(s)" in out

    def test_renders_odata_value_envelope(self):
        payload = {"value": [{"id": "u-1", "name": "Legacy"}]}
        out = ArchitectAgent._compact_list_result_for_history(json.dumps(payload))
        assert out is not None
        assert "Legacy" in out and "u-1" in out

    def test_full_page_of_metrics_keeps_every_name_and_shrinks_payload(self):
        """A 20-item paginated list_metrics with 200-char descriptions
        easily exceeds the iteration prompt's per-result budget when
        serialized as JSON. The compact renderer must (a) keep every
        name visible to the LLM and (b) shrink the payload meaningfully
        compared to raw JSON.
        """
        items = [self._metric(i, desc_chars=200) for i in range(20)]
        payload = {
            "results": items,
            "_pagination": {"returned": 20, "has_more": False},
        }
        raw = json.dumps(payload)
        out = ArchitectAgent._compact_list_result_for_history(raw)
        assert out is not None

        for i in range(20):
            assert f"Metric {i}" in out, f"Metric {i} missing from compact output"
        # Naive 4000-char truncation of the raw JSON would hide items;
        # the compact form must be substantially smaller than the raw.
        assert len(raw) > 5000
        assert len(out) < len(raw) * 0.6, (
            f"compact output ({len(out)} chars) should be much smaller "
            f"than raw JSON ({len(raw)} chars)"
        )

    def test_paginated_envelope_includes_has_more_hint(self):
        items = [self._metric(i, desc_chars=20) for i in range(20)]
        payload = {
            "results": items,
            "_pagination": {
                "returned": 20,
                "has_more": True,
                "next_skip": 20,
                "hint": "use $filter or skip=20",
            },
        }
        out = ArchitectAgent._compact_list_result_for_history(json.dumps(payload))
        assert out is not None
        assert "has_more" not in out  # we don't dump raw key names
        assert "more pages available" in out
        assert "next_skip=20" in out
        assert "$filter" in out
        for i in range(20):
            assert f"Metric {i}" in out

    def test_paginated_envelope_no_more_pages(self):
        payload = {
            "results": [self._metric(0, desc_chars=10)],
            "_pagination": {"returned": 1, "has_more": False},
        }
        out = ArchitectAgent._compact_list_result_for_history(json.dumps(payload))
        assert out is not None
        assert "no more pages" in out
        assert "next_skip" not in out

    def test_long_descriptions_are_truncated_per_item(self):
        items = [self._metric(0, desc_chars=500)]
        out = ArchitectAgent._compact_list_result_for_history(
            json.dumps(items), desc_chars=100
        )
        assert out is not None
        assert "Metric 0" in out
        assert "x" * 500 not in out
        assert "…" in out

    def test_extras_rendered_for_known_keys(self):
        items = [
            {
                "id": "u-1",
                "name": "Quality",
                "description": "d",
                "score_type": "numeric",
                "metric_scope": "endpoint",
            }
        ]
        out = ArchitectAgent._compact_list_result_for_history(json.dumps(items))
        assert out is not None
        assert "score_type=numeric" in out
        assert "metric_scope=endpoint" in out

    def test_caps_displayed_items_when_page_huge(self):
        items = [
            {"id": f"u-{i}", "name": f"Item {i}", "description": "d"}
            for i in range(80)
        ]
        out = ArchitectAgent._compact_list_result_for_history(
            json.dumps(items), max_items=10
        )
        assert out is not None
        assert "Item 0" in out
        assert "Item 9" in out
        assert "Item 10" not in out
        assert "70 more item(s) on this page" in out

    def test_non_dict_items_fall_back(self):
        """Lists of primitives (e.g. tag strings) shouldn't be rendered
        as entity lists — let the caller fall back to plain truncation.
        """
        out = ArchitectAgent._compact_list_result_for_history(
            json.dumps(["a", "b", "c"])
        )
        assert out is None

    def test_format_history_uses_compact_renderer_for_lists(self):
        """End-to-end: feeding a 20-item paginated list_metrics result
        into _execution_history must surface every metric name in
        _format_history(), not silently truncate after the first few.
        This is the regression that made the architect think metrics
        didn't exist on the platform.
        """
        agent = _make_agent(_mock_model())
        items = [
            {
                "id": f"00000000-0000-0000-0000-{i:012d}",
                "name": f"Metric {i}",
                "description": "y" * 200,
                "score_type": "binary",
                "metric_scope": "endpoint",
            }
            for i in range(20)
        ]
        payload = json.dumps(
            {
                "results": items,
                "_pagination": {"returned": 20, "has_more": True, "next_skip": 20},
            }
        )
        agent._execution_history.append(
            ExecutionStep(
                iteration=1,
                reasoning="discover existing metrics",
                action="call_tool",
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="list_metrics",
                        success=True,
                        content=payload,
                    )
                ],
            )
        )

        formatted = agent._format_history()
        for i in range(20):
            assert f"Metric {i}" in formatted, (
                f"Metric {i} missing from _format_history output — the "
                f"compact renderer is not being applied"
            )
        assert "more pages available" in formatted

    def test_format_history_falls_back_for_non_list_results(self):
        """Single-object tool results must not be munged — pass-through
        with the existing truncation behaviour.
        """
        agent = _make_agent(_mock_model())
        agent._execution_history.append(
            ExecutionStep(
                iteration=1,
                reasoning="get a single metric",
                action="call_tool",
                tool_calls=[],
                tool_results=[
                    ToolResult(
                        tool_name="get_metric",
                        success=True,
                        content=json.dumps(
                            {"id": "u-1", "name": "Solo", "description": "single item"}
                        ),
                    )
                ],
            )
        )
        formatted = agent._format_history()
        assert "Solo" in formatted
        assert "List response" not in formatted


# ── Mapping completion tests ─────────────────────────────────────


@pytest.mark.unit
class TestArchitectMappingMatch:
    """Behavior-metric mapping progress tracking via _match_mapping.

    The matcher must require BOTH a behavior name match AND a metric
    that is in that mapping's planned metrics list. Mappings with
    multiple planned metrics must accumulate links across calls and
    only flip to completed once every planned metric is linked.
    """

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @staticmethod
    def _travel_plan():
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )

        return ArchitectPlan(
            behaviors=[
                BehaviorSpec(name="Core Travel Assistance", description="d"),
                BehaviorSpec(name="Pricing Information & Disclaimers", description="d"),
                BehaviorSpec(name="Refuses Non-Travel Queries", description="d"),
            ],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[
                MetricSpec(name="Pricing Information Accuracy", description="d"),
                MetricSpec(name="Travel Hallucination Detection", description="d"),
                MetricSpec(name="Domain Adherence", description="d"),
            ],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Core Travel Assistance",
                    metrics=[
                        "Pricing Information Accuracy",
                        "Travel Hallucination Detection",
                    ],
                ),
                MappingSpec(
                    behavior="Pricing Information & Disclaimers",
                    metrics=[
                        "Pricing Information Accuracy",
                        "Travel Hallucination Detection",
                    ],
                ),
                MappingSpec(
                    behavior="Refuses Non-Travel Queries",
                    metrics=["Domain Adherence"],
                ),
            ],
        )

    @staticmethod
    def _link_call(behavior_id: str, metric_id: str):
        from rhesis.sdk.agents.schemas import ToolCall

        return ToolCall(
            tool_name="add_behavior_to_metric",
            arguments=json.dumps(
                {"behavior_id": behavior_id, "metric_id": metric_id}
            ),
        )

    def test_single_metric_mapping_completes_on_first_link(self, mock_model):
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {
            "b-refuses": "Refuses Non-Travel Queries",
            "m-domain": "Domain Adherence",
        }

        updated = agent._match_mapping(
            plan,
            self._link_call("b-refuses", "m-domain"),
            agent._id_to_name,
        )

        refuses = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Refuses Non-Travel Queries"
        )
        assert updated is True
        assert refuses.completed is True
        assert refuses.linked_metrics == ["Domain Adherence"]

    def test_multi_metric_mapping_requires_all_links_before_completion(self, mock_model):
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {
            "b-core": "Core Travel Assistance",
            "m-pricing": "Pricing Information Accuracy",
            "m-hallucination": "Travel Hallucination Detection",
        }

        agent._match_mapping(
            plan,
            self._link_call("b-core", "m-pricing"),
            agent._id_to_name,
        )

        core = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Core Travel Assistance"
        )
        assert core.completed is False
        assert core.linked_metrics == ["Pricing Information Accuracy"]

        agent._match_mapping(
            plan,
            self._link_call("b-core", "m-hallucination"),
            agent._id_to_name,
        )

        assert core.completed is True
        assert set(core.linked_metrics) == {
            "Pricing Information Accuracy",
            "Travel Hallucination Detection",
        }

    def test_overlapping_metrics_do_not_cross_contaminate_mappings(self, mock_model):
        """Linking metric M to behavior A must not mark a different mapping
        (B → M) as completed, even though M appears in both mappings."""
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {
            "b-core": "Core Travel Assistance",
            "b-pricing": "Pricing Information & Disclaimers",
            "m-pricing": "Pricing Information Accuracy",
            "m-hallucination": "Travel Hallucination Detection",
        }

        # Fully link Core Travel Assistance.
        agent._match_mapping(
            plan,
            self._link_call("b-core", "m-pricing"),
            agent._id_to_name,
        )
        agent._match_mapping(
            plan,
            self._link_call("b-core", "m-hallucination"),
            agent._id_to_name,
        )

        core = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Core Travel Assistance"
        )
        pricing = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Pricing Information & Disclaimers"
        )
        assert core.completed is True
        # Critical assertion: Pricing's mapping must remain pending — the
        # OR-based matcher would have flipped it via the shared metric.
        assert pricing.completed is False
        assert pricing.linked_metrics == []

    def test_no_match_when_metric_not_in_mapping(self, mock_model):
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {
            "b-refuses": "Refuses Non-Travel Queries",
            "m-pricing": "Pricing Information Accuracy",
        }

        updated = agent._match_mapping(
            plan,
            self._link_call("b-refuses", "m-pricing"),
            agent._id_to_name,
        )

        refuses = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Refuses Non-Travel Queries"
        )
        assert updated is False
        assert refuses.completed is False
        assert refuses.linked_metrics == []

    def test_no_match_when_ids_not_in_id_to_name(self, mock_model):
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {}  # neither id resolved

        updated = agent._match_mapping(
            plan,
            self._link_call("b-core", "m-pricing"),
            agent._id_to_name,
        )

        assert updated is False
        for mapping in plan.behavior_metric_mappings:
            assert mapping.completed is False
            assert mapping.linked_metrics == []

    @pytest.mark.asyncio
    async def test_save_plan_validation_failure_has_actionable_error(
        self, mock_model, caplog
    ):
        """save_plan should reject malformed args, log the offending input,
        and return a structured field-level error for the LLM to act on."""
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)

        # Plan missing required top-level keys and with a bad enum value.
        bad_args = {
            "behaviors": [
                {"name": "Safety", "reuse_status": "Reuse"},  # wrong literal case
            ],
            # test_sets and metrics intentionally omitted.
        }
        tc = ToolCall(
            tool_name="save_plan",
            arguments=json.dumps(bad_args),
        )

        with caplog.at_level("WARNING"):
            result = await agent._execute_save_plan(tc)

        assert result.success is False
        assert "Plan validation failed" in result.error
        # Field-level pinpointing: at least one of the problems should be
        # named in the error message.
        assert (
            "test_sets" in result.error
            or "metrics" in result.error
            or "reuse_status" in result.error
        )
        # The agent's plan must remain unchanged (None here) when validation
        # failed — no partial mutation.
        assert agent._plan is None
        # The log must carry the offending args for diagnosability.
        joined_log = " | ".join(r.getMessage() for r in caplog.records)
        assert "save_plan failed" in joined_log
        assert "args:" in joined_log

    @pytest.mark.asyncio
    async def test_save_plan_seeds_id_to_name_from_existing_ids(self, mock_model):
        """When the LLM saves a plan with existing_id for reused entities,
        those (id, name) pairs must be available for _match_mapping even
        if the agent never re-calls list_behaviors / list_metrics."""
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        plan_payload = ArchitectPlan(
            behaviors=[
                BehaviorSpec(
                    name="Refuses Non-Travel Queries",
                    description="d",
                    reuse_status="reuse",
                    existing_id="b-refuses",
                ),
            ],
            test_sets=[TestSetSpec(name="Tests", description="d")],
            metrics=[
                MetricSpec(
                    name="Domain Adherence",
                    description="d",
                    reuse_status="reuse",
                    existing_id="m-domain",
                ),
            ],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Refuses Non-Travel Queries",
                    metrics=["Domain Adherence"],
                ),
            ],
        ).model_dump()

        save = ToolCall(
            tool_name="save_plan",
            arguments=json.dumps(plan_payload),
        )
        result = await agent._execute_save_plan(save)
        assert result.success is True

        assert agent._id_to_name["b-refuses"] == "Refuses Non-Travel Queries"
        assert agent._id_to_name["m-domain"] == "Domain Adherence"

        # Now exercise add_behavior_to_metric without ever calling list_*.
        agent._match_mapping(
            agent._plan,
            self._link_call("b-refuses", "m-domain"),
            agent._id_to_name,
        )
        refuses = agent._plan.behavior_metric_mappings[0]
        assert refuses.completed is True
        assert refuses.linked_metrics == ["Domain Adherence"]

    def test_idempotent_repeated_link_call(self, mock_model):
        agent = _make_agent(mock_model)
        plan = self._travel_plan()
        agent._plan = plan
        agent._id_to_name = {
            "b-refuses": "Refuses Non-Travel Queries",
            "m-domain": "Domain Adherence",
        }

        # First call links and completes the single-metric mapping.
        first = agent._match_mapping(
            plan,
            self._link_call("b-refuses", "m-domain"),
            agent._id_to_name,
        )
        # Second call is a no-op (no state change).
        second = agent._match_mapping(
            plan,
            self._link_call("b-refuses", "m-domain"),
            agent._id_to_name,
        )

        refuses = next(
            m for m in plan.behavior_metric_mappings
            if m.behavior == "Refuses Non-Travel Queries"
        )
        assert first is True
        assert second is False
        assert refuses.completed is True
        assert refuses.linked_metrics == ["Domain Adherence"]


@pytest.mark.unit
class TestArchitectIdCollectionUngated:
    """_collect_id_names runs on every successful tool call, not only
    once a plan is saved. Otherwise IDs gathered during the planning
    phase (list_behaviors, list_metrics) are dropped."""

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @pytest.mark.asyncio
    async def test_ids_collected_before_plan_saved(self, mock_model, monkeypatch):
        from rhesis.sdk.agents.base import BaseAgent
        from rhesis.sdk.agents.schemas import ToolCall, ToolResult

        agent = _make_agent(mock_model)
        assert agent._plan is None  # planning phase

        async def _fake_execute(self, tc):
            return ToolResult(
                tool_name=tc.tool_name,
                success=True,
                content=json.dumps({
                    "results": [
                        {"id": "uuid-1", "name": "Safety"},
                        {"id": "uuid-2", "name": "Accuracy"},
                    ],
                    "_pagination": {"returned": 2, "has_more": False},
                }),
            )

        monkeypatch.setattr(BaseAgent, "execute_tool", _fake_execute)

        await agent.execute_tool(
            ToolCall(tool_name="list_behaviors", arguments=json.dumps({}))
        )

        assert agent._id_to_name["uuid-1"] == "Safety"
        assert agent._id_to_name["uuid-2"] == "Accuracy"


# ── Plan progress rendering ──────────────────────────────────────


@pytest.mark.unit
class TestArchitectPlanProgress:
    """The iteration prompt must surface plan-completion progress as a
    short, machine-readable line so the LLM can reason about ordering
    on its own — specifically, that ``generate_test_set`` and
    ``create_test_set_bulk`` are blocked until every behavior, metric,
    and behavior→metric mapping is marked completed.

    The runtime constraint in ``_check_execution_order`` is the
    authoritative gate; the prompt text is what makes that gate
    visible to the LLM (rather than hiding tools, which is opaque).
    """

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @staticmethod
    def _tools_list() -> list:
        return [
            {"name": "create_behavior", "description": "Create behavior"},
            {"name": "create_metric", "description": "Create metric"},
            {"name": "add_behavior_to_metric", "description": "Link"},
            {"name": "generate_test_set", "description": "Generate test set"},
            {"name": "create_test_set_bulk", "description": "Bulk import"},
            {"name": "list_metrics", "description": "Discover metrics"},
        ]

    @staticmethod
    def _ready_plan():
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )

        return ArchitectPlan(
            behaviors=[BehaviorSpec(name="Safety", description="d", completed=True)],
            metrics=[MetricSpec(name="Quality", description="d", completed=True)],
            test_sets=[TestSetSpec(name="Smoke", description="d", num_tests=5)],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Safety",
                    metrics=["Quality"],
                    linked_metrics=["Quality"],
                    completed=True,
                )
            ],
        )

    @staticmethod
    def _pending_mapping_plan():
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )

        return ArchitectPlan(
            behaviors=[BehaviorSpec(name="Safety", description="d", completed=True)],
            metrics=[MetricSpec(name="Quality", description="d", completed=True)],
            test_sets=[TestSetSpec(name="Smoke", description="d", num_tests=5)],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Safety",
                    metrics=["Quality"],
                    linked_metrics=[],
                    completed=False,
                )
            ],
        )

    @staticmethod
    def _pending_metric_plan():
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MetricSpec,
            TestSetSpec,
        )

        return ArchitectPlan(
            behaviors=[
                BehaviorSpec(name="Safety", description="d", completed=True),
                BehaviorSpec(name="Accuracy", description="d", completed=True),
            ],
            metrics=[MetricSpec(name="Quality", description="d", completed=False)],
            test_sets=[TestSetSpec(name="Smoke", description="d", num_tests=5)],
        )

    def test_progress_string_is_empty_without_plan(self, mock_model):
        agent = _make_agent(mock_model)
        assert agent._format_plan_progress() == ""

    def test_progress_string_lists_each_category_with_ratios(self, mock_model):
        agent = _make_agent(mock_model)
        agent._plan = self._pending_metric_plan()

        progress = agent._format_plan_progress()
        assert "behaviors 2/2" in progress
        assert "metrics 0/1" in progress
        assert "mappings 0/0" in progress
        assert "test_sets 0/1" in progress

    def test_progress_string_marks_test_set_generation_blocked_while_pending(
        self, mock_model
    ):
        agent = _make_agent(mock_model)
        agent._plan = self._pending_mapping_plan()

        progress = agent._format_plan_progress()
        assert "test-set generation: blocked" in progress
        assert "N/N" in progress

    def test_progress_string_marks_test_set_generation_ready_when_done(
        self, mock_model
    ):
        agent = _make_agent(mock_model)
        agent._plan = self._ready_plan()

        progress = agent._format_plan_progress()
        assert "test-set generation: ready" in progress
        assert "blocked" not in progress

    def test_build_prompt_includes_progress_line_when_plan_present(self, mock_model):
        """End-to-end: the iteration prompt the LLM sees must contain
        the progress line so the LLM can reason about ordering. Match
        the literal substring — drift here is the regression we care
        about.
        """
        agent = _make_agent(mock_model)
        agent._plan = self._pending_mapping_plan()

        prompt = agent._build_prompt("hi", self._tools_list())
        assert "Plan progress:" in prompt
        assert "test-set generation: blocked" in prompt

    def test_build_prompt_omits_progress_line_without_plan(self, mock_model):
        """No plan → no progress line. We don't want to inject empty
        boilerplate into prompts for ad-hoc, pre-plan turns.
        """
        agent = _make_agent(mock_model)
        prompt = agent._build_prompt("hi", self._tools_list())
        assert "Plan progress:" not in prompt

    def test_test_set_tools_remain_visible_in_prompt_regardless_of_plan_state(
        self, mock_model
    ):
        """We deliberately do NOT hide tools from the LLM. The
        principled mechanism is: prompt advertises preconditions,
        runtime constraint enforces them. This test guards against
        re-introducing silent tool filtering.
        """
        agent = _make_agent(mock_model)
        agent._plan = self._pending_mapping_plan()

        prompt = agent._build_prompt("hi", self._tools_list())
        assert "generate_test_set" in prompt
        assert "create_test_set_bulk" in prompt


@pytest.mark.unit
class TestArchitectSavePlanReconciliation:
    """save_plan reconciles plan completion against session evidence.

    Real conversations frequently end up with the LLM creating
    behaviors, metrics and behavior-metric links *before* it ever
    calls ``save_plan`` (for example, after exploration, when the
    user keeps refining the plan as it's being built). When the plan
    finally arrives, every ``completed`` defaults to False — which
    causes ``_check_execution_order`` to block ``generate_test_set``
    even though every prerequisite is already on the platform.

    These tests pin the recovery path: ``_execute_save_plan`` consults
    the agent's session evidence (``_id_to_name`` for created
    behaviors/metrics, ``_linked_pairs`` for completed mappings) and
    flips the matching plan items to ``completed=True`` automatically.
    """

    @pytest.fixture
    def mock_model(self):
        return _mock_model()

    @staticmethod
    def _plan_payload():
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )

        return ArchitectPlan(
            behaviors=[
                BehaviorSpec(name="Provides Accurate Health Info", description="d"),
            ],
            test_sets=[TestSetSpec(name="Health Tests", description="d")],
            metrics=[
                MetricSpec(name="Health Information Accuracy", description="d"),
            ],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Provides Accurate Health Info",
                    metrics=["Health Information Accuracy"],
                ),
            ],
        ).model_dump()

    @staticmethod
    def _save_call(payload):
        from rhesis.sdk.agents.schemas import ToolCall

        return ToolCall(tool_name="save_plan", arguments=json.dumps(payload))

    @staticmethod
    def _link_call(behavior_id, metric_id):
        from rhesis.sdk.agents.schemas import ToolCall

        return ToolCall(
            tool_name="add_behavior_to_metric",
            arguments=json.dumps(
                {"behavior_id": behavior_id, "metric_id": metric_id}
            ),
        )

    @pytest.mark.asyncio
    async def test_entities_created_before_plan_are_marked_completed(
        self, mock_model
    ):
        """Reproduces the failing session in the worker logs:
        create_behavior + create_metric run while ``self._plan is None``,
        then save_plan arrives. Without reconciliation, every plan item
        comes back ``completed=False`` and generate_test_set is rejected
        forever."""
        agent = _make_agent(mock_model)

        agent._id_to_name = {
            "b-health": "Provides Accurate Health Info",
            "m-health": "Health Information Accuracy",
        }
        agent._behavior_id_names = {"b-health": "Provides Accurate Health Info"}
        agent._metric_id_names = {"m-health": "Health Information Accuracy"}

        result = await agent._execute_save_plan(self._save_call(self._plan_payload()))
        assert result.success is True

        plan = agent._plan
        assert plan is not None
        assert plan.behaviors[0].completed is True
        assert plan.metrics[0].completed is True

    @pytest.mark.asyncio
    async def test_links_made_before_plan_complete_their_mappings_on_save(
        self, mock_model
    ):
        """``add_behavior_to_metric`` succeeded before save_plan, so
        ``_linked_pairs`` carries the (behavior, metric) pair across
        the plan-save boundary. After save, the matching MappingSpec
        must be marked completed and ``linked_metrics`` populated."""
        agent = _make_agent(mock_model)

        agent._id_to_name = {
            "b-health": "Provides Accurate Health Info",
            "m-health": "Health Information Accuracy",
        }
        agent._behavior_id_names = {"b-health": "Provides Accurate Health Info"}
        agent._metric_id_names = {"m-health": "Health Information Accuracy"}
        agent._record_link_if_mapping(
            self._link_call("b-health", "m-health")
        )
        assert agent._linked_pairs == {
            ("provides accurate health info", "health information accuracy")
        }

        result = await agent._execute_save_plan(self._save_call(self._plan_payload()))
        assert result.success is True

        mapping = agent._plan.behavior_metric_mappings[0]
        assert mapping.completed is True
        assert mapping.linked_metrics == ["Health Information Accuracy"]

    @pytest.mark.asyncio
    async def test_existing_id_alone_is_enough_to_mark_completed(self, mock_model):
        """Reused entities have ``existing_id`` set; that is sufficient
        evidence that the entity is on the platform, regardless of
        ``reuse_status``."""
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MetricSpec,
            TestSetSpec,
        )

        agent = _make_agent(mock_model)

        plan_payload = ArchitectPlan(
            behaviors=[
                BehaviorSpec(
                    name="Existing Behavior",
                    description="d",
                    reuse_status="new",  # deliberately not "reuse"
                    existing_id="b-existing",
                ),
            ],
            test_sets=[TestSetSpec(name="T", description="d")],
            metrics=[
                MetricSpec(
                    name="Existing Metric",
                    description="d",
                    reuse_status="new",
                    existing_id="m-existing",
                ),
            ],
        ).model_dump()

        result = await agent._execute_save_plan(self._save_call(plan_payload))
        assert result.success is True
        assert agent._plan.behaviors[0].completed is True
        assert agent._plan.metrics[0].completed is True

    @pytest.mark.asyncio
    async def test_reconcile_does_not_complete_unmatched_items(self, mock_model):
        """Items whose names don't appear anywhere in session evidence
        must stay ``completed=False`` so the execution-order guard can
        still catch genuine gaps."""
        agent = _make_agent(mock_model)

        # Only one of the two planned entities was actually created.
        agent._id_to_name = {"b-health": "Provides Accurate Health Info"}
        agent._behavior_id_names = {"b-health": "Provides Accurate Health Info"}
        # _metric_id_names intentionally empty — metric was never observed

        result = await agent._execute_save_plan(self._save_call(self._plan_payload()))
        assert result.success is True

        plan = agent._plan
        assert plan.behaviors[0].completed is True
        assert plan.metrics[0].completed is False
        assert plan.behavior_metric_mappings[0].completed is False
        assert plan.behavior_metric_mappings[0].linked_metrics == []

    @pytest.mark.asyncio
    async def test_partial_link_keeps_multi_metric_mapping_pending(self, mock_model):
        """A mapping with two planned metrics where only one has been
        linked must report exactly that single link and remain
        ``completed=False`` until the second link arrives."""
        from rhesis.sdk.agents.architect.plan import (
            ArchitectPlan,
            BehaviorSpec,
            MappingSpec,
            MetricSpec,
            TestSetSpec,
        )

        agent = _make_agent(mock_model)

        agent._id_to_name = {
            "b-core": "Core",
            "m-pricing": "Pricing Accuracy",
            "m-hallucination": "Hallucination Detection",
        }
        agent._behavior_id_names = {"b-core": "Core"}
        agent._metric_id_names = {
            "m-pricing": "Pricing Accuracy",
            "m-hallucination": "Hallucination Detection",
        }
        # Only one of the two required metrics has been linked so far.
        agent._record_link_if_mapping(self._link_call("b-core", "m-pricing"))

        plan_payload = ArchitectPlan(
            behaviors=[BehaviorSpec(name="Core", description="d")],
            test_sets=[TestSetSpec(name="T", description="d")],
            metrics=[
                MetricSpec(name="Pricing Accuracy", description="d"),
                MetricSpec(name="Hallucination Detection", description="d"),
            ],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Core",
                    metrics=["Pricing Accuracy", "Hallucination Detection"],
                ),
            ],
        ).model_dump()

        result = await agent._execute_save_plan(self._save_call(plan_payload))
        assert result.success is True

        mapping = agent._plan.behavior_metric_mappings[0]
        assert mapping.linked_metrics == ["Pricing Accuracy"]
        assert mapping.completed is False

    @pytest.mark.asyncio
    async def test_llm_supplied_completed_flags_are_ignored(self, mock_model):
        """The LLM cannot fast-track or sandbag plan progress by writing
        ``completed`` itself — those values are stripped before validation
        and the runtime fills them from session evidence alone."""
        agent = _make_agent(mock_model)

        # No session evidence at all — every item must come back False
        # even though the LLM tried to set completed=True.
        bad_payload = self._plan_payload()
        bad_payload["behaviors"][0]["completed"] = True
        bad_payload["metrics"][0]["completed"] = True
        bad_payload["behavior_metric_mappings"][0]["completed"] = True
        bad_payload["behavior_metric_mappings"][0]["linked_metrics"] = [
            "Health Information Accuracy"
        ]

        result = await agent._execute_save_plan(self._save_call(bad_payload))
        assert result.success is True

        plan = agent._plan
        assert plan.behaviors[0].completed is False
        assert plan.metrics[0].completed is False
        assert plan.behavior_metric_mappings[0].completed is False
        assert plan.behavior_metric_mappings[0].linked_metrics == []

    def test_record_link_ignores_unrelated_tool_calls(self, mock_model):
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)
        agent._id_to_name = {"b-x": "B", "m-x": "M"}

        agent._record_link_if_mapping(
            ToolCall(
                tool_name="create_behavior",
                arguments=json.dumps({"behavior_id": "b-x", "metric_id": "m-x"}),
            )
        )
        assert agent._linked_pairs == set()

    def test_record_link_skips_name_pair_when_ids_not_resolved(self, mock_model):
        """When IDs aren't in _id_to_name yet, no name-based pair is stored,
        but the raw ID pair is always recorded as a fallback."""
        agent = _make_agent(mock_model)
        agent._id_to_name = {}  # neither id known yet
        agent._record_link_if_mapping(self._link_call("b-x", "m-x"))
        assert agent._linked_pairs == set()  # name pair not stored
        assert agent._linked_id_pairs == {("b-x", "m-x")}  # ID fallback stored

    def test_linked_pairs_cleared_on_reset(self, mock_model):
        agent = _make_agent(mock_model)
        agent._linked_pairs.add(("b", "m"))
        agent._linked_id_pairs.add(("bid", "mid"))
        agent.reset()
        assert agent._linked_pairs == set()
        assert agent._linked_id_pairs == set()

    @pytest.mark.asyncio
    async def test_execution_order_reconciles_before_checking(self, mock_model):
        """generate_test_set is allowed when all links exist in _linked_pairs,
        even if save_plan was not called again after the links were made."""
        from rhesis.sdk.agents.schemas import ToolCall

        agent = _make_agent(mock_model)

        # Build a plan with one behavior, one metric, one mapping — all
        # marked incomplete (as the LLM would supply them).
        payload = self._plan_payload()
        await agent._execute_save_plan(self._save_call(payload))
        assert agent._plan is not None

        # Manually mark all behaviours and metrics as having been created,
        # and record the behavior→metric link — without calling save_plan.
        agent._id_to_name["b-id"] = "Provides Accurate Health Info"
        agent._id_to_name["m-id"] = "Health Information Accuracy"
        agent._behavior_id_names["b-id"] = "Provides Accurate Health Info"
        agent._metric_id_names["m-id"] = "Health Information Accuracy"
        agent._linked_pairs.add(("provides accurate health info", "health information accuracy"))

        tc = ToolCall(tool_name="generate_test_set", arguments=json.dumps({}))
        result = agent._check_execution_order(tc)

        # The guard must pass (return None) because the session evidence
        # proves everything is done.
        assert result is None


class TestArchitectFormatAttachments:
    """``_format_attachments`` must read the canonical ``extracted_text``
    key shared with the rest of the pipeline, while still tolerating
    legacy payloads that carry ``content`` for backward compatibility.
    """

    @pytest.fixture
    def mock_model(self):
        model = Mock(spec=BaseLLM)
        model.a_generate = AsyncMock(return_value={})
        return model

    def test_reads_extracted_text(self, mock_model):
        agent = _make_agent(mock_model)
        agent._attachments = {
            "files": [
                {
                    "filename": "spec.pdf",
                    "content_type": "application/pdf",
                    "extracted_text": "  payload via the new key  ",
                }
            ]
        }

        rendered = agent._format_attachments()
        assert "spec.pdf" in rendered
        assert "payload via the new key" in rendered

    def test_falls_back_to_legacy_content_key(self, mock_model):
        agent = _make_agent(mock_model)
        agent._attachments = {
            "files": [
                {
                    "filename": "old.pdf",
                    "content_type": "application/pdf",
                    "content": "legacy payload",
                }
            ]
        }

        rendered = agent._format_attachments()
        assert "old.pdf" in rendered
        assert "legacy payload" in rendered

    def test_prefers_extracted_text_when_both_present(self, mock_model):
        """If a producer accidentally emits both keys, the canonical one wins."""
        agent = _make_agent(mock_model)
        agent._attachments = {
            "files": [
                {
                    "filename": "both.pdf",
                    "content_type": "application/pdf",
                    "extracted_text": "modern",
                    "content": "legacy",
                }
            ]
        }

        rendered = agent._format_attachments()
        assert "modern" in rendered
        assert "legacy" not in rendered

    def test_returns_empty_string_when_no_attachments(self, mock_model):
        agent = _make_agent(mock_model)
        agent._attachments = None
        assert agent._format_attachments() == ""

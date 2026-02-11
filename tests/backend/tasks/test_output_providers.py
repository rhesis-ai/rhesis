"""
Tests for output providers (OutputProvider implementations).

Covers all 5 output providers:
- SingleTurnOutput: live endpoint invocation
- MultiTurnOutput: live Penelope agent execution
- TestResultOutput: re-scoring from stored TestResult
- TraceOutput: evaluation from stored single-turn traces (root span)
- MultiTurnTraceOutput: placeholder for multi-turn trace evaluation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.tasks.execution.executors.output_providers import (
    MultiTurnOutput,
    MultiTurnTraceOutput,
    OutputProvider,
    SingleTurnOutput,
    TestOutput,
    TestResultOutput,
    TraceOutput,
    get_provider_metadata,
)

# ============================================================================
# TestOutput dataclass tests
# ============================================================================


class TestTestOutput:
    """Tests for the TestOutput dataclass."""

    def test_default_values(self):
        """TestOutput defaults: execution_time=0, metrics={}, source='live'."""
        output = TestOutput(response={"output": "hello"})
        assert output.response == {"output": "hello"}
        assert output.execution_time == 0.0
        assert output.metrics == {}
        assert output.source == "live"

    def test_custom_values(self):
        """TestOutput accepts custom values for all fields."""
        output = TestOutput(
            response={"output": "hello"},
            execution_time=42.5,
            metrics={"accuracy": 0.9},
            source="test_result",
        )
        assert output.execution_time == 42.5
        assert output.metrics == {"accuracy": 0.9}
        assert output.source == "test_result"


# ============================================================================
# OutputProvider ABC tests
# ============================================================================


class TestOutputProviderABC:
    """Tests for the OutputProvider abstract base class."""

    def test_cannot_instantiate(self):
        """OutputProvider is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OutputProvider()

    def test_subclass_must_implement_get_output(self):
        """A subclass that doesn't implement get_output cannot be instantiated."""

        class IncompleteProvider(OutputProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()


# ============================================================================
# SingleTurnOutput tests
# ============================================================================


class TestSingleTurnOutput:
    """Tests for the SingleTurnOutput provider."""

    @pytest.mark.asyncio
    async def test_invokes_endpoint_and_returns_output(self):
        """SingleTurnOutput calls EndpointService and returns TestOutput."""
        mock_endpoint_service = AsyncMock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(return_value={"output": "hello world"})

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.process_endpoint_result",
                return_value={"output": "hello world"},
            ) as mock_process,
        ):
            provider = SingleTurnOutput()
            output = await provider.get_output(
                db=MagicMock(),
                endpoint_id="ep-123",
                prompt_content="What is 2+2?",
                organization_id="org-1",
                user_id="user-1",
            )

        assert isinstance(output, TestOutput)
        assert output.response == {"output": "hello world"}
        assert output.execution_time > 0 or output.execution_time == 0
        assert output.source == "live"
        mock_endpoint_service.invoke_endpoint.assert_called_once()
        mock_process.assert_called_once_with({"output": "hello world"})

    @pytest.mark.asyncio
    async def test_passes_test_execution_context(self):
        """SingleTurnOutput forwards test_execution_context to invoke_endpoint."""
        mock_endpoint_service = AsyncMock()
        mock_endpoint_service.invoke_endpoint = AsyncMock(return_value={"output": "ok"})
        ctx = {"test_run_id": "run-1", "test_id": "test-1"}

        with (
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.get_endpoint_service",
                return_value=mock_endpoint_service,
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.process_endpoint_result",
                return_value={"output": "ok"},
            ),
        ):
            provider = SingleTurnOutput()
            await provider.get_output(
                db=MagicMock(),
                endpoint_id="ep-123",
                prompt_content="prompt",
                organization_id="org-1",
                user_id="user-1",
                test_execution_context=ctx,
            )

        call_kwargs = mock_endpoint_service.invoke_endpoint.call_args.kwargs
        assert call_kwargs["test_execution_context"] == ctx


# ============================================================================
# MultiTurnOutput tests
# ============================================================================


class TestMultiTurnOutput:
    """Tests for the MultiTurnOutput provider."""

    @pytest.mark.asyncio
    async def test_runs_penelope_and_returns_output_with_metrics(self):
        """MultiTurnOutput runs PenelopeAgent and returns metrics from the trace."""
        mock_penelope_result = MagicMock()
        mock_penelope_result.model_dump.return_value = {
            "conversation_summary": [{"penelope_message": "Hi", "target_response": "Hello"}],
            "metrics": {"goal_achieved": True},
        }

        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_test.return_value = mock_penelope_result
        mock_agent_class.return_value = mock_agent_instance

        mock_test = MagicMock()
        mock_test.test_configuration = {
            "goal": "Greet the user",
            "max_turns": 3,
        }

        # PenelopeAgent is imported lazily; BackendEndpointTarget needs mocking too
        with (
            patch(
                "rhesis.penelope.PenelopeAgent",
                mock_agent_class,
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.BackendEndpointTarget",
            ),
        ):
            provider = MultiTurnOutput(model="gpt-4")
            output = await provider.get_output(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-123",
                organization_id="org-1",
                user_id="user-1",
            )

        assert isinstance(output, TestOutput)
        assert output.metrics == {"goal_achieved": True}
        # Metrics should be popped from response
        assert "metrics" not in output.response
        assert output.source == "live"
        mock_agent_instance.execute_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_model_when_none(self):
        """MultiTurnOutput creates PenelopeAgent without model when model is None."""
        mock_penelope_result = MagicMock()
        mock_penelope_result.model_dump.return_value = {
            "conversation_summary": [],
            "metrics": {},
        }

        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_instance.execute_test.return_value = mock_penelope_result
        mock_agent_class.return_value = mock_agent_instance

        mock_test = MagicMock()
        mock_test.test_configuration = {"goal": "Test goal"}

        # PenelopeAgent is imported lazily; BackendEndpointTarget needs mocking too
        with (
            patch(
                "rhesis.penelope.PenelopeAgent",
                mock_agent_class,
            ),
            patch(
                "rhesis.backend.tasks.execution.executors.output_providers.BackendEndpointTarget",
            ),
        ):
            provider = MultiTurnOutput(model=None)
            await provider.get_output(
                db=MagicMock(),
                test=mock_test,
                endpoint_id="ep-1",
                organization_id="org-1",
                user_id="user-1",
            )

        # When model is None, PenelopeAgent() is called with no args
        mock_agent_class.assert_called_once_with()


# ============================================================================
# TestResultOutput tests
# ============================================================================


class TestTestResultOutput:
    """Tests for the TestResultOutput provider (re-scoring)."""

    @pytest.mark.asyncio
    async def test_loads_stored_output(self):
        """TestResultOutput loads output from stored TestResult via CRUD."""
        mock_result = MagicMock()
        mock_result.test_output = {"output": "stored response"}

        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_test_results",
            return_value=[mock_result],
        ):
            provider = TestResultOutput(reference_test_run_id="run-abc")
            output = await provider.get_output(
                db=MagicMock(),
                test_id="test-123",
                organization_id="org-1",
                user_id="user-1",
            )

        assert isinstance(output, TestOutput)
        assert output.response == {"output": "stored response"}
        assert output.execution_time == 0
        assert output.source == "test_result"

    @pytest.mark.asyncio
    async def test_raises_when_no_stored_output(self):
        """TestResultOutput raises ValueError when no stored output is found."""
        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_test_results",
            return_value=[],
        ):
            provider = TestResultOutput(reference_test_run_id="run-abc")
            with pytest.raises(ValueError, match="No stored output"):
                await provider.get_output(
                    db=MagicMock(),
                    test_id="test-123",
                    organization_id="org-1",
                )

    @pytest.mark.asyncio
    async def test_raises_when_output_is_none(self):
        """TestResultOutput raises ValueError when test_output is None."""
        mock_result = MagicMock()
        mock_result.test_output = None

        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_test_results",
            return_value=[mock_result],
        ):
            provider = TestResultOutput(reference_test_run_id="run-abc")
            with pytest.raises(ValueError, match="No stored output"):
                await provider.get_output(
                    db=MagicMock(),
                    test_id="test-999",
                )

    @pytest.mark.asyncio
    async def test_odata_filter_string(self):
        """TestResultOutput builds the correct OData filter for multi-tenant safe lookup."""
        mock_result = MagicMock()
        mock_result.test_output = {"output": "ok"}

        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_test_results",
            return_value=[mock_result],
        ) as mock_get:
            provider = TestResultOutput(reference_test_run_id="run-xyz")
            await provider.get_output(
                db=MagicMock(),
                test_id="test-42",
                organization_id="org-1",
                user_id="user-1",
            )

        call_kwargs = mock_get.call_args
        filter_arg = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        if filter_arg is None:
            # positional args
            filter_arg = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
        assert "run-xyz" in str(filter_arg)
        assert "test-42" in str(filter_arg)


# ============================================================================
# TraceOutput tests
# ============================================================================


def _make_span(
    *,
    parent_span_id=None,
    span_name="test_span",
    attributes=None,
    events=None,
):
    """Helper to create a mock trace span."""
    span = MagicMock()
    span.parent_span_id = parent_span_id
    span.span_name = span_name
    span.attributes = attributes or {}
    span.events = events or []
    return span


class TestTraceOutput:
    """Tests for the TraceOutput provider (single-turn trace evaluation)."""

    # ------------------------------------------------------------------
    # get_output integration
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_raises_when_no_traces(self):
        """TraceOutput raises ValueError when no traces are found."""
        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_trace_by_id",
            return_value=[],
        ):
            provider = TraceOutput(trace_id="trace-missing")
            with pytest.raises(ValueError, match="No traces found"):
                await provider.get_output(
                    db=MagicMock(),
                    organization_id="org-1",
                )

    @pytest.mark.asyncio
    async def test_passes_project_id(self):
        """TraceOutput passes project_id to crud.get_trace_by_id."""
        root = _make_span(
            attributes={"gen_ai.completion": "response"},
            span_name="test",
        )

        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_trace_by_id",
            return_value=[root],
        ) as mock_get:
            provider = TraceOutput(trace_id="t-1", project_id="proj-99")
            await provider.get_output(
                db=MagicMock(),
                organization_id="org-1",
            )

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["trace_id"] == "t-1"
        assert call_kwargs["project_id"] == "proj-99"

    @pytest.mark.asyncio
    async def test_returns_trace_source(self):
        """TraceOutput returns source='trace' and execution_time=0."""
        root = _make_span(
            attributes={"ai.agent.input": "hi", "ai.agent.output": "hey"},
        )

        with patch(
            "rhesis.backend.tasks.execution.executors.output_providers.crud.get_trace_by_id",
            return_value=[root],
        ):
            provider = TraceOutput(trace_id="t-1")
            output = await provider.get_output(db=MagicMock(), organization_id="org-1")

        assert isinstance(output, TestOutput)
        assert output.source == "trace"
        assert output.execution_time == 0

    # ------------------------------------------------------------------
    # _find_root_span
    # ------------------------------------------------------------------

    def test_find_root_span_returns_span_with_null_parent(self):
        """Root span is the one with parent_span_id=None."""
        child = _make_span(parent_span_id="abc123", span_name="child")
        root = _make_span(parent_span_id=None, span_name="root")
        provider = TraceOutput(trace_id="t-1")

        assert provider._find_root_span([child, root]) is root

    def test_find_root_span_returns_empty_string_parent(self):
        """Root span also matches parent_span_id='' (empty string)."""
        child = _make_span(parent_span_id="abc123", span_name="child")
        root = _make_span(parent_span_id="", span_name="root")
        provider = TraceOutput(trace_id="t-1")

        assert provider._find_root_span([child, root]) is root

    def test_find_root_span_falls_back_to_first(self):
        """When no span has null parent_span_id, first span is used."""
        s1 = _make_span(parent_span_id="aaa", span_name="first")
        s2 = _make_span(parent_span_id="bbb", span_name="second")
        provider = TraceOutput(trace_id="t-1")

        assert provider._find_root_span([s1, s2]) is s1

    # ------------------------------------------------------------------
    # Event-based extraction (highest priority)
    # ------------------------------------------------------------------

    def test_extracts_from_agent_events(self):
        """Agent-level events (ai.agent.input/output) are extracted."""
        root = _make_span(
            events=[
                {
                    "name": "ai.agent.input",
                    "attributes": {"ai.agent.input": "user question"},
                },
                {
                    "name": "ai.agent.output",
                    "attributes": {"ai.agent.output": "agent answer"},
                },
            ],
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "user question"
        assert response["output"] == "agent answer"

    def test_extracts_from_llm_events(self):
        """LLM-level events (ai.prompt/ai.completion) are extracted."""
        root = _make_span(
            events=[
                {
                    "name": "ai.prompt",
                    "attributes": {
                        "ai.prompt.role": "user",
                        "ai.prompt.content": "What is AI?",
                    },
                },
                {
                    "name": "ai.completion",
                    "attributes": {
                        "ai.completion.content": "AI is ...",
                    },
                },
            ],
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "What is AI?"
        assert response["output"] == "AI is ..."

    def test_agent_events_take_priority_over_llm_events(self):
        """When both agent and LLM events exist, agent wins."""
        root = _make_span(
            events=[
                {
                    "name": "ai.agent.input",
                    "attributes": {"ai.agent.input": "agent in"},
                },
                {
                    "name": "ai.prompt",
                    "attributes": {
                        "ai.prompt.content": "llm prompt",
                    },
                },
                {
                    "name": "ai.agent.output",
                    "attributes": {
                        "ai.agent.output": "agent out",
                    },
                },
                {
                    "name": "ai.completion",
                    "attributes": {
                        "ai.completion.content": "llm completion",
                    },
                },
            ],
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "agent in"
        assert response["output"] == "agent out"

    # ------------------------------------------------------------------
    # Attribute-based extraction (fallback)
    # ------------------------------------------------------------------

    def test_extracts_from_agent_attributes(self):
        """Agent-level attributes are used when no events are present."""
        root = _make_span(
            attributes={
                "ai.agent.input": "attr input",
                "ai.agent.output": "attr output",
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "attr input"
        assert response["output"] == "attr output"

    def test_extracts_from_function_attributes(self):
        """function.kwargs / function.result are used as fallback."""
        root = _make_span(
            attributes={
                "function.kwargs": '{"query": "test"}',
                "function.result": '{"answer": "42"}',
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == '{"query": "test"}'
        assert response["output"] == '{"answer": "42"}'

    def test_extracts_from_legacy_gen_ai_attributes(self):
        """Legacy gen_ai.prompt / gen_ai.completion work as last resort."""
        root = _make_span(
            attributes={
                "gen_ai.prompt": "What is AI?",
                "gen_ai.completion": "AI is ...",
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "What is AI?"
        assert response["output"] == "AI is ..."

    def test_attribute_priority_order(self):
        """Agent attrs take priority over function attrs and legacy."""
        root = _make_span(
            attributes={
                "ai.agent.input": "agent",
                "function.kwargs": "func",
                "gen_ai.prompt": "legacy",
                "ai.agent.output": "agent out",
                "function.result": "func out",
                "gen_ai.completion": "legacy out",
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "agent"
        assert response["output"] == "agent out"

    # ------------------------------------------------------------------
    # Mixed event + attribute scenarios
    # ------------------------------------------------------------------

    def test_events_take_priority_over_attributes(self):
        """Events are checked before attributes."""
        root = _make_span(
            events=[
                {
                    "name": "ai.agent.input",
                    "attributes": {"ai.agent.input": "event input"},
                },
                {
                    "name": "ai.agent.output",
                    "attributes": {
                        "ai.agent.output": "event output",
                    },
                },
            ],
            attributes={
                "ai.agent.input": "attr input",
                "ai.agent.output": "attr output",
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "event input"
        assert response["output"] == "event output"

    def test_event_input_with_attr_output(self):
        """Input from events, output falls back to attributes."""
        root = _make_span(
            events=[
                {
                    "name": "ai.prompt",
                    "attributes": {
                        "ai.prompt.content": "event prompt",
                    },
                },
            ],
            attributes={
                "gen_ai.completion": "attr completion",
            },
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "event prompt"
        assert response["output"] == "attr completion"

    # ------------------------------------------------------------------
    # Last-resort fallback
    # ------------------------------------------------------------------

    def test_fallback_to_span_name_and_empty_output(self):
        """When no events or attributes, uses span_name and empty output."""
        root = _make_span(
            span_name="my_endpoint_call",
            attributes={},
            events=[],
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "my_endpoint_call"
        assert response["output"] == ""

    # ------------------------------------------------------------------
    # Root span selection with multiple spans
    # ------------------------------------------------------------------

    def test_uses_root_span_not_child_spans(self):
        """Only the root span's events/attributes are used."""
        root = _make_span(
            parent_span_id=None,
            events=[
                {
                    "name": "ai.agent.input",
                    "attributes": {"ai.agent.input": "root input"},
                },
                {
                    "name": "ai.agent.output",
                    "attributes": {
                        "ai.agent.output": "root output",
                    },
                },
            ],
        )
        child = _make_span(
            parent_span_id="root-span-id",
            events=[
                {
                    "name": "ai.prompt",
                    "attributes": {
                        "ai.prompt.content": "child prompt",
                    },
                },
                {
                    "name": "ai.completion",
                    "attributes": {
                        "ai.completion.content": "child completion",
                    },
                },
            ],
        )
        provider = TraceOutput(trace_id="t-1")
        # Child comes first in the list (ordered by start_time)
        response = provider._build_response_from_traces([child, root])

        assert response["input"] == "root input"
        assert response["output"] == "root output"

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_events_list(self):
        """Empty events list falls through to attributes."""
        root = _make_span(
            events=[],
            attributes={"function.kwargs": "input", "function.result": "output"},
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        assert response["input"] == "input"
        assert response["output"] == "output"

    def test_event_with_missing_attributes(self):
        """Events with missing attribute keys are skipped."""
        root = _make_span(
            events=[
                {"name": "ai.prompt", "attributes": {}},
                {
                    "name": "ai.completion",
                    "attributes": {
                        "ai.completion.content": "the answer",
                    },
                },
            ],
            attributes={"gen_ai.prompt": "fallback input"},
        )
        provider = TraceOutput(trace_id="t-1")
        response = provider._build_response_from_traces([root])

        # Input: event had empty ai.prompt.content (None), so falls to attrs
        assert response["input"] == "fallback input"
        assert response["output"] == "the answer"


# ============================================================================
# MultiTurnTraceOutput tests
# ============================================================================


class TestMultiTurnTraceOutput:
    """Tests for the MultiTurnTraceOutput placeholder."""

    def test_stores_session_id_and_project_id(self):
        """Constructor stores session_id and project_id."""
        provider = MultiTurnTraceOutput(session_id="sess-abc", project_id="proj-1")
        assert provider.session_id == "sess-abc"
        assert provider.project_id == "proj-1"

    def test_project_id_defaults_to_none(self):
        """project_id is optional and defaults to None."""
        provider = MultiTurnTraceOutput(session_id="sess-1")
        assert provider.project_id is None

    @pytest.mark.asyncio
    async def test_raises_not_implemented(self):
        """get_output raises NotImplementedError (placeholder)."""
        provider = MultiTurnTraceOutput(session_id="sess-abc")
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await provider.get_output(db=MagicMock(), organization_id="org-1")

    @pytest.mark.asyncio
    async def test_error_message_includes_session_id(self):
        """NotImplementedError message includes the session_id."""
        provider = MultiTurnTraceOutput(session_id="sess-xyz")
        with pytest.raises(NotImplementedError, match="sess-xyz"):
            await provider.get_output(db=MagicMock(), organization_id="org-1")


# ============================================================================
# get_provider_metadata tests
# ============================================================================


class TestGetProviderMetadata:
    """Tests for the get_provider_metadata helper function."""

    def test_returns_none_for_none_provider(self):
        """None provider (live execution) returns None metadata."""
        assert get_provider_metadata(None) is None

    def test_returns_none_for_single_turn_output(self):
        """SingleTurnOutput (live) returns None metadata."""
        provider = SingleTurnOutput()
        assert get_provider_metadata(provider) is None

    def test_returns_none_for_multi_turn_output(self):
        """MultiTurnOutput (live) returns None metadata."""
        provider = MultiTurnOutput(model="gpt-4")
        assert get_provider_metadata(provider) is None

    def test_rescore_metadata(self):
        """TestResultOutput returns source='rescore' and reference_test_run_id."""
        provider = TestResultOutput(reference_test_run_id="run-abc-123")
        meta = get_provider_metadata(provider)

        assert meta is not None
        assert meta["source"] == "rescore"
        assert meta["reference_test_run_id"] == "run-abc-123"

    def test_trace_metadata(self):
        """TraceOutput returns source='trace' and trace_id."""
        provider = TraceOutput(trace_id="trace-xyz")
        meta = get_provider_metadata(provider)

        assert meta is not None
        assert meta["source"] == "trace"
        assert meta["trace_id"] == "trace-xyz"
        assert "project_id" not in meta

    def test_trace_metadata_with_project_id(self):
        """TraceOutput includes project_id when set."""
        provider = TraceOutput(trace_id="t-1", project_id="proj-99")
        meta = get_provider_metadata(provider)

        assert meta["source"] == "trace"
        assert meta["trace_id"] == "t-1"
        assert meta["project_id"] == "proj-99"

    def test_multi_turn_trace_metadata(self):
        """MultiTurnTraceOutput returns source='multi_turn_trace' and session_id."""
        provider = MultiTurnTraceOutput(session_id="sess-abc")
        meta = get_provider_metadata(provider)

        assert meta is not None
        assert meta["source"] == "multi_turn_trace"
        assert meta["session_id"] == "sess-abc"
        assert "project_id" not in meta

    def test_multi_turn_trace_metadata_with_project_id(self):
        """MultiTurnTraceOutput includes project_id when set."""
        provider = MultiTurnTraceOutput(session_id="sess-1", project_id="proj-1")
        meta = get_provider_metadata(provider)

        assert meta["source"] == "multi_turn_trace"
        assert meta["session_id"] == "sess-1"
        assert meta["project_id"] == "proj-1"

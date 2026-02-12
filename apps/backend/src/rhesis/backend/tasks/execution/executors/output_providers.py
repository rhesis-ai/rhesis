"""
Output providers for test execution.

Provides different strategies for obtaining test output:
- SingleTurnOutput: Live invocation of an endpoint (single-turn tests)
- MultiTurnOutput: Live Penelope conversation agent execution (multi-turn tests)
- TestResultOutput: Cached output from a previous TestResult (re-scoring)
- TraceOutput: Output extracted from stored OpenTelemetry traces

All providers return a TestOutput dataclass, enabling the runner to evaluate
metrics uniformly regardless of how the output was obtained.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from rhesis.backend.app import crud
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.tasks.execution.executors.results import (
    process_endpoint_result,
)
from rhesis.backend.tasks.execution.penelope_target import (
    BackendEndpointTarget,
)


@dataclass
class TestOutput:
    """Output from a test, regardless of how it was obtained."""

    response: Dict[str, Any]  # Endpoint response or Penelope trace
    execution_time: float = 0.0  # ms; 0 for stored outputs
    metrics: Dict[str, Any] = field(default_factory=dict)  # Pre-evaluated (Penelope)
    source: str = "live"  # "live" | "test_result" | "trace"


class OutputProvider(ABC):
    """Gets test output from some source."""

    @abstractmethod
    async def get_output(self, **kwargs) -> TestOutput:
        """Obtain test output from the provider's source.

        Each provider accepts keyword arguments relevant to its source.
        Common kwargs include: db, endpoint_id, organization_id, user_id,
        test_id, prompt_content, test_execution_context, test.

        Returns:
            TestOutput containing the response and metadata.
        """
        ...


class SingleTurnOutput(OutputProvider):
    """Live output for single-turn tests -- invokes the endpoint.

    Uses EndpointService.invoke_endpoint() (from app.dependencies)
    and process_endpoint_result() (from executors.results).
    """

    async def get_output(
        self,
        *,
        db,
        endpoint_id,
        prompt_content,
        organization_id,
        user_id,
        test_execution_context=None,
        **kwargs,
    ) -> TestOutput:
        start_time = datetime.now(timezone.utc)

        # Reuse existing EndpointService singleton
        endpoint_service = get_endpoint_service()
        result = await endpoint_service.invoke_endpoint(
            db=db,
            endpoint_id=endpoint_id,
            input_data={"input": prompt_content},
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
        )
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Reuse existing result processing (ErrorResponse handling, output extraction)
        processed = process_endpoint_result(result)
        return TestOutput(response=processed, execution_time=execution_time)


class MultiTurnOutput(OutputProvider):
    """Live output for multi-turn tests -- runs the Penelope conversation agent.

    Uses BackendEndpointTarget (from penelope_target) for endpoint integration
    and PenelopeAgent (from rhesis.penelope) for conversation execution.
    """

    def __init__(self, model=None):
        self.model = model

    async def get_output(
        self,
        *,
        db,
        test,
        endpoint_id,
        organization_id,
        user_id,
        test_execution_context=None,
        **kwargs,
    ) -> TestOutput:
        start_time = datetime.now(timezone.utc)

        # Extract multi-turn configuration from test
        test_config = test.test_configuration or {}
        goal = test_config["goal"]
        instructions = test_config.get("instructions")
        scenario = test_config.get("scenario")
        restrictions = test_config.get("restrictions")
        context = test_config.get("context")
        max_turns = test_config.get("max_turns", 10)

        # Reuse existing PenelopeAgent and BackendEndpointTarget
        from rhesis.penelope import PenelopeAgent

        agent = PenelopeAgent(model=self.model) if self.model else PenelopeAgent()

        target = BackendEndpointTarget(
            db=db,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
        )

        penelope_result = agent.execute_test(
            target=target,
            goal=goal,
            instructions=instructions,
            scenario=scenario,
            restrictions=restrictions,
            context=context,
            max_turns=max_turns,
        )
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        trace = penelope_result.model_dump(mode="json")
        metrics = trace.pop("metrics", {})

        # Penelope evaluates metrics internally -> return them with the output
        return TestOutput(
            response=trace,
            execution_time=execution_time,
            metrics=metrics,
        )


class TestResultOutput(OutputProvider):
    """Stored output from a previous TestResult -- works for any test type.

    Uses crud.get_test_results() with OData filter for multi-tenant safe lookup.
    """

    def __init__(self, reference_test_run_id: str):
        # Validate UUID format to prevent malformed filter strings
        UUID(reference_test_run_id)
        self.reference_test_run_id = reference_test_run_id

    async def get_output(
        self,
        *,
        db,
        test_id,
        organization_id=None,
        user_id=None,
        **kwargs,
    ) -> TestOutput:
        # Validate test_id format before interpolating into filter
        UUID(str(test_id))

        # Reuse existing CRUD with OData filter (multi-tenant safe)
        filter_str = f"test_run_id eq {self.reference_test_run_id} and test_id eq {test_id}"
        results = crud.get_test_results(
            db,
            limit=1,
            filter=filter_str,
            organization_id=organization_id,
            user_id=user_id,
        )

        if not results or not results[0].test_output:
            raise ValueError(
                f"No stored output for test {test_id} in run {self.reference_test_run_id}"
            )

        logger.debug(
            f"[TestResultOutput] Loaded stored output for test {test_id} "
            f"from run {self.reference_test_run_id}"
        )

        return TestOutput(
            response=results[0].test_output,
            execution_time=0,
            source="test_result",
        )


class TraceOutput(OutputProvider):
    """Stored output from Trace records -- single-turn tests.

    A single trace_id maps to multiple spans (one per LLM call, tool call,
    etc.).  The **root span** (``parent_span_id IS NULL``) carries the
    top-level input/output of the endpoint invocation.

    Input/output storage conventions (in priority order):

    1. **Span events** -- the SDK records ``ai.prompt`` events (with
       ``ai.prompt.content``) and ``ai.completion`` events (with
       ``ai.completion.content``).  Agent-level I/O uses ``ai.agent.input``
       / ``ai.agent.output`` events.
    2. **Span attributes** -- ``ai.agent.input`` / ``ai.agent.output``
       attributes, or ``function.kwargs`` / ``function.result``.
    3. **Legacy attributes** -- ``gen_ai.prompt`` / ``gen_ai.completion``
       (older OpenTelemetry semantic conventions).

    Uses ``crud.get_trace_by_id()`` for multi-tenant safe lookup.  The
    returned spans are ordered by ``start_time``; the first span with
    ``parent_span_id IS NULL`` is treated as the root.
    """

    def __init__(self, trace_id: str, project_id: Optional[str] = None):
        self.trace_id = trace_id
        self.project_id = project_id

    async def get_output(
        self,
        *,
        db,
        organization_id,
        test_id=None,
        **kwargs,
    ) -> TestOutput:
        # Reuse existing CRUD for trace retrieval
        traces = crud.get_trace_by_id(
            db,
            trace_id=self.trace_id,
            project_id=self.project_id,
            organization_id=organization_id,
        )

        if not traces:
            raise ValueError(f"No traces found for trace_id {self.trace_id}")

        # Extract input/output from the root span
        response = self._build_response_from_traces(traces)
        return TestOutput(response=response, execution_time=0, source="trace")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_root_span(self, traces):
        """Return the root span (parent_span_id is None/empty).

        Falls back to the first span if no explicit root is found.
        """
        for span in traces:
            if not span.parent_span_id:
                return span
        return traces[0]

    def _build_response_from_traces(self, traces) -> Dict[str, Any]:
        """Extract input/output from the root span of a single-turn trace.

        Extraction priority (first non-empty value wins):

        1. **Events** on the root span:
           - ``ai.agent.input`` event  -> input
           - ``ai.agent.output`` event -> output
           - ``ai.prompt`` event       -> input  (LLM-level)
           - ``ai.completion`` event   -> output (LLM-level)

        2. **Attributes** on the root span:
           - ``ai.agent.input``  / ``ai.agent.output``
           - ``function.kwargs`` / ``function.result``
           - ``gen_ai.prompt``   / ``gen_ai.completion``  (legacy)

        3. **Fallback**: ``span_name`` as input, empty string as output.

        Returns:
            Dict with ``input`` and ``output`` keys.
        """
        root = self._find_root_span(traces)
        input_text: Optional[str] = None
        output_text: Optional[str] = None

        # --- 1. Extract from span events (preferred) ---
        events = root.events or []
        input_text, output_text = self._extract_from_events(events)

        # --- 2. Extract from span attributes (fallback) ---
        if input_text is None or output_text is None:
            attrs = root.attributes or {}
            attr_input, attr_output = self._extract_from_attributes(attrs)
            if input_text is None:
                input_text = attr_input
            if output_text is None:
                output_text = attr_output

        # --- 3. Last-resort fallback ---
        if input_text is None:
            input_text = root.span_name or ""
        if output_text is None:
            output_text = ""

        return {"input": input_text, "output": output_text}

    @staticmethod
    def _extract_from_events(events) -> tuple:
        """Extract input/output from span events.

        Returns:
            (input_text, output_text) -- either may be None.
        """
        input_text: Optional[str] = None
        output_text: Optional[str] = None

        for event in events:
            name = event.get("name", "") if isinstance(event, dict) else ""
            event_attrs = event.get("attributes", {}) if isinstance(event, dict) else {}

            # Agent-level events (highest priority for root span)
            if name == "ai.agent.input" and input_text is None:
                input_text = event_attrs.get("ai.agent.input")
            elif name == "ai.agent.output" and output_text is None:
                output_text = event_attrs.get("ai.agent.output")
            # LLM-level events
            elif name == "ai.prompt" and input_text is None:
                input_text = event_attrs.get("ai.prompt.content")
            elif name == "ai.completion" and output_text is None:
                output_text = event_attrs.get("ai.completion.content")

        return input_text, output_text

    @staticmethod
    def _extract_from_attributes(attrs: Dict[str, Any]) -> tuple:
        """Extract input/output from span attributes.

        Returns:
            (input_text, output_text) -- either may be None.
        """
        input_text: Optional[str] = None
        output_text: Optional[str] = None

        # Agent-level attributes
        if attrs.get("ai.agent.input"):
            input_text = attrs["ai.agent.input"]
        if attrs.get("ai.agent.output"):
            output_text = attrs["ai.agent.output"]

        # Function I/O attributes
        if input_text is None and attrs.get("function.kwargs"):
            input_text = attrs["function.kwargs"]
        if output_text is None and attrs.get("function.result"):
            output_text = attrs["function.result"]

        # Legacy OpenTelemetry semantic conventions
        if input_text is None and attrs.get("gen_ai.prompt"):
            input_text = attrs["gen_ai.prompt"]
        if output_text is None and attrs.get("gen_ai.completion"):
            output_text = attrs["gen_ai.completion"]

        return input_text, output_text


class MultiTurnTraceOutput(OutputProvider):
    """Placeholder for multi-turn trace evaluation.

    Multi-turn conversations share a ``conversation_id`` (stored as
    ``ai.session.id`` in the span ``attributes`` JSONB column).
    Each turn produces a separate trace; all traces in a conversation
    must be collected and ordered to reconstruct the conversation.

    This provider is **not yet fully implemented**.  When ready it
    will:
    1. Query all root spans where
       ``attributes->>'ai.session.id' = <conversation_id>``.
    2. Order them by ``start_time``.
    3. Build a ``conversation_summary`` list suitable for
       ``evaluate_multi_turn_metrics()``.

    For now the class exists so callers can detect and handle the
    multi-turn trace path without runtime errors.
    """

    def __init__(
        self,
        conversation_id: str,
        project_id: Optional[str] = None,
    ):
        self.conversation_id = conversation_id
        self.project_id = project_id

    async def get_output(
        self,
        *,
        db,
        organization_id,
        **kwargs,
    ) -> TestOutput:
        raise NotImplementedError(
            "Multi-turn trace evaluation is not yet implemented. "
            f"conversation_id={self.conversation_id}"
        )


# ============================================================================
# Provenance helpers
# ============================================================================


def get_provider_metadata(
    provider: Optional[OutputProvider],
) -> Optional[Dict[str, Any]]:
    """Build provenance metadata dict from an OutputProvider.

    Returns ``None`` when the provider is ``None`` (live execution) so
    callers can skip the metadata key entirely.

    The returned dict is stored in ``test_metrics.metadata`` on the
    ``TestResult`` record, making it easy to identify:

    * **source** -- ``"rescore"`` | ``"trace"`` | ``"live"``
    * **reference_test_run_id** -- original run (re-score only)
    * **trace_id** / **project_id** -- trace identifiers (trace only)
    * **conversation_id** -- multi-turn trace conversation (placeholder)
    """
    if provider is None:
        return None

    if isinstance(provider, TestResultOutput):
        return {
            "source": "rescore",
            "reference_test_run_id": provider.reference_test_run_id,
        }

    if isinstance(provider, TraceOutput):
        meta: Dict[str, Any] = {
            "source": "trace",
            "trace_id": provider.trace_id,
        }
        if provider.project_id:
            meta["project_id"] = provider.project_id
        return meta

    if isinstance(provider, MultiTurnTraceOutput):
        meta = {
            "source": "multi_turn_trace",
            "conversation_id": provider.conversation_id,
        }
        if provider.project_id:
            meta["project_id"] = provider.project_id
        return meta

    # Live providers (SingleTurnOutput, MultiTurnOutput) -> no metadata
    return None

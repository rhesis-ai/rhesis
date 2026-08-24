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

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

if TYPE_CHECKING:
    pass

from rhesis.backend.app import crud
from rhesis.backend.app.crud.telemetry import get_trace_by_id
from rhesis.backend.app.dependencies import get_endpoint_service
from rhesis.backend.app.services.endpoint.result_processing import process_endpoint_result

logger = logging.getLogger(__name__)


def _load_run_params(db, test_execution_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Load resolved parameter snapshot from the TestRun attributes.

    Returns an empty dict when no parameters are available, so callers
    can always do ``if params: input_data["params"] = params``.
    """
    if not test_execution_context:
        return {}
    test_run_id = test_execution_context.get("test_run_id")
    if not test_run_id:
        return {}
    try:
        from rhesis.backend.app.models.test_run import TestRun

        run = db.query(TestRun).filter(TestRun.id == UUID(test_run_id)).first()
        if run and run.attributes:
            return run.attributes.get("parameters") or {}
    except Exception as e:
        logger.warning("Failed to load run parameters for %s: %s", test_run_id, e)
    return {}


@dataclass
class TestOutput:
    """Output from a test, regardless of how it was obtained."""

    response: Dict[str, Any]  # Endpoint response or Penelope trace
    execution_time: float = 0.0  # ms; 0 for stored outputs
    metrics: Dict[str, Any] = field(default_factory=dict)  # Pre-evaluated (Penelope)
    source: str = "live"  # "live" | "test_result" | "trace"
    # False only for a live multi-turn run whose evaluation contract could not be interpreted
    # confidently. The conversation is then not run at all (nothing it produced could be
    # scored), so this arrives with an empty `metrics` and an error `response`.
    #
    # Still a separate field rather than inferred from `metrics` being falsy: that already
    # means "this is stored/trace output, evaluate externally", and callers fork on it, so an
    # unusable-contract run would otherwise be routed into full external re-evaluation
    # instead of Error. Callers must short-circuit to Error when this is False -- see
    # `executors.runners.MultiTurnRunner.run`.
    contract_usable: bool = True


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

    def __init__(self, model=None):
        self.model = model

    async def get_output(
        self,
        *,
        db,
        endpoint_id,
        prompt_content,
        organization_id,
        user_id,
        test_execution_context=None,
        test_id=None,
        params=None,
        **kwargs,
    ) -> TestOutput:
        start_time = datetime.now(timezone.utc)

        input_data = {"input": prompt_content}

        # Inject resolved experiment parameters so REST request mappings
        # can reference {{ params.model }}, {{ params.temperature }}, etc.
        if params is None:
            params = _load_run_params(db, test_execution_context)
        if params:
            input_data["params"] = params

        # Inject file data if the test has attached files
        if test_id:
            input_files = self._load_input_files(db, test_id, organization_id)
            if input_files:
                input_data["files"] = input_files

        # Reuse existing EndpointService singleton
        endpoint_service = get_endpoint_service()
        result = await endpoint_service.invoke_endpoint(
            db=db,
            endpoint_id=endpoint_id,
            input_data=input_data,
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
        )
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Reuse existing result processing (ErrorResponse handling, output extraction)
        processed = process_endpoint_result(result)
        return TestOutput(response=processed, execution_time=execution_time)

    @staticmethod
    def _load_input_files(db, test_id, organization_id):
        """Load files attached to a test and return them as FileReference metadata.

        No bytes are loaded, no base64 encoding, no extraction — extraction was
        performed at upload time and is available on ``File.extracted_text``.
        """
        from rhesis.backend.app.models.file import File
        from rhesis.sdk.connector.types import FileReference

        try:
            files = (
                db.query(File)
                .filter(
                    File.entity_id == test_id,
                    File.entity_type == "Test",
                    File.deleted_at.is_(None),
                )
                .order_by(File.position)
                .all()
            )

            return [
                FileReference(
                    id=str(f.id),
                    filename=f.filename,
                    content_type=f.content_type,
                    size_bytes=f.size_bytes,
                    content_hash=f.content_hash or "",
                    storage_path=f.storage_path,
                    extracted_text=f.extracted_text,
                )
                for f in files
                if f.storage_path  # only include files that have been migrated to storage
            ]
        except Exception as e:
            # Promote to ERROR with full traceback: silently dropping
            # attached files causes downstream tests to run without
            # context the user expected to provide.  Returning [] keeps
            # the test runnable; the operator must catch this in the logs.
            logger.error(
                "Failed to load input files for test %s — test will execute "
                "WITHOUT its attached file context: %s",
                test_id,
                e,
                exc_info=True,
            )
            return []


def resolve_multi_turn_contract(
    db, test, user_id: Optional[str]
) -> tuple[Optional[Dict[str, Any]], bool]:
    """Resolve and validate the evaluation contract for a multi-turn test.

    Interprets lazily (on first call for this test's current wording) and reuses the cached
    result otherwise -- see ``services/test_interpretation.ensure_contract``. Shared by both
    live execution paths (here, and ``batch/invocation.py``'s ``_run_multi_turn``) so there is
    one place that decides what "usable" means, not two that could drift.

    Returns ``(contract, usable)``:
      - ``contract`` is a plain dict ready for ``PenelopeAgent.execute_test(contract=...)``,
        or ``None`` when there is nothing usable to pass -- Penelope then falls back to
        scoring the raw ``goal`` exactly as it did before evaluation contracts existed.
      - ``usable`` is False when the test could not be interpreted confidently enough to
        score. Callers must then discard whatever metrics the run produces: a low-confidence
        or uninterpretable test must report Error, never a Pass/Fail nobody should trust.

    "Nothing to interpret" and "interpretation failed" are deliberately different answers.
    A config with no ``goal`` was never a candidate for interpretation, so it returns
    ``(None, True)`` and scores the legacy way -- matching what the re-score path in
    ``evaluation.py`` does with a test that has no stored contract. Only an actual
    interpretation attempt that came back unusable returns ``(None, False)``. Conflating the
    two made a test report Error for the sole reason that it had nothing to interpret.
    """
    from rhesis.backend.app.services.test_interpretation import (
        contract_usability,
        ensure_contract,
        is_multi_turn_config,
    )

    if not is_multi_turn_config(getattr(test, "test_configuration", None) or {}):
        return None, True

    evaluation_contract = ensure_contract(db, test, user_id=user_id)
    usable, reason = contract_usability(evaluation_contract)
    if not usable:
        logger.warning("[MultiTurn] Test %s has no usable evaluation contract: %s", test.id, reason)
        return None, False
    return evaluation_contract.model_dump(mode="json", exclude_none=True), True


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
        params=None,
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
        max_turns = test_config.get("max_turns") or 10
        min_turns = test_config.get("min_turns")

        contract, contract_usable = resolve_multi_turn_contract(db, test, user_id)

        # Nothing this run could produce would be scoreable, so don't run it. Every verdict
        # would be discarded downstream anyway; conducting the full conversation first would
        # bill the org for target calls and judge tokens with a guaranteed-Error outcome.
        if not contract_usable:
            logger.info(
                "[MultiTurn] Skipping conversation for test %s: evaluation contract is not "
                "usable, so no verdict from this run could be trusted",
                test.id,
            )
            return TestOutput(
                response={
                    "status": "error",
                    "error": (
                        "The test could not be interpreted well enough to score, so it was not run."
                    ),
                },
                execution_time=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
                metrics={},
                contract_usable=False,
            )

        # Load files attached to the test (reuse SingleTurnOutput's static method)
        input_files = SingleTurnOutput._load_input_files(db, test.id, organization_id)

        if params is None:
            params = _load_run_params(db, test_execution_context)

        from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
        from rhesis.backend.app.utils.user_model_utils import ensure_language_model
        from rhesis.backend.tasks.execution.penelope_target import (
            BackendEndpointTarget,
        )
        from rhesis.penelope import PenelopeAgent

        # Both branches stamped -- see the fuller note in batch/runner.py.
        agent = (
            PenelopeAgent(model=ensure_language_model(self.model))
            if self.model
            else PenelopeAgent()
        )
        stamp_usage_provenance(agent.model, metered=True)

        target = BackendEndpointTarget(
            db=db,
            endpoint_id=endpoint_id,
            organization_id=organization_id,
            user_id=user_id,
            test_execution_context=test_execution_context,
            params=params,
        )

        penelope_result = agent.execute_test(
            target=target,
            goal=goal,
            instructions=instructions,
            scenario=scenario,
            restrictions=restrictions,
            context=context,
            max_turns=max_turns,
            min_turns=min_turns,
            files=input_files if input_files else None,
            contract=contract,
        )
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        trace = penelope_result.model_dump(mode="json")
        penelope_metrics = trace.pop("metrics", {})

        # Penelope evaluates metrics internally -> return them with the output.
        return TestOutput(
            response=trace,
            execution_time=execution_time,
            metrics=penelope_metrics,
            contract_usable=True,
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

    Uses ``get_trace_by_id()`` for multi-tenant safe lookup.  The
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
        traces = get_trace_by_id(
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

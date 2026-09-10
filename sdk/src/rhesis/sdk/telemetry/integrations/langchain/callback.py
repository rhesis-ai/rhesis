"""LangChain callback handler for OpenTelemetry tracing.

Translates LangChain's callback events into Rhesis ``ai.*`` spans. Where a span
belongs in the run tree, and when it ends, is
:class:`~rhesis.sdk.telemetry.integrations.langchain.span_registry.SpanRegistry`'s
job; this module only decides what each event means.
"""

import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.integrations.langchain.extractors import (
    MAX_CONTENT_LENGTH,
    extract_agent_input,
    extract_agent_name,
    extract_agent_output,
    extract_retriever_backend,
    extract_tool_output,
    should_trace_chain,
    summarize_documents,
)
from rhesis.sdk.telemetry.integrations.langchain.llm_processing import (
    add_chat_prompt_event,
    extract_and_set_tokens,
    set_llm_attributes,
)
from rhesis.sdk.telemetry.integrations.langchain.span_registry import SpanRegistry
from rhesis.sdk.telemetry.integrations.langchain.turns import claim_turn_root, resolve_turn
from rhesis.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.context import is_llm_observation_active, is_tracing_disabled
from rhesis.telemetry.schemas import AIOperationType

logger = logging.getLogger(__name__)

# Tools named this way are a delegation, not a call: LangGraph's supervisor and
# swarm patterns both hand off by having the model call transfer_to_<agent>.
HANDOFF_TOOL_PREFIX = "transfer_to_"

# Every span carries the short form of its operation as an attribute alongside
# the full ai.<domain>.<action> span name.
_OPERATION_ATTRIBUTE = {
    AIOperationType.LLM_INVOKE: AIAttributes.OPERATION_LLM_INVOKE,
    AIOperationType.TOOL_INVOKE: AIAttributes.OPERATION_TOOL_INVOKE,
    AIOperationType.RETRIEVAL: AIAttributes.OPERATION_RETRIEVAL,
    AIOperationType.AGENT_INVOKE: AIAttributes.OPERATION_AGENT_INVOKE,
    AIOperationType.AGENT_HANDOFF: AIAttributes.OPERATION_AGENT_HANDOFF,
}


class RhesisSpanRecorder:
    """Records Rhesis spans from LangChain callback events.

    Deliberately not a ``BaseCallbackHandler`` subclass: langchain_core is an
    optional dependency, so the base class can only be imported at call time.
    :func:`create_langchain_callback` mixes the two together, which keeps this
    class importable - and unit testable - without langchain installed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tracer = trace.get_tracer(__name__)
        self._registry = SpanRegistry()

    # =====================================================================
    # Span helpers shared by the event handlers
    # =====================================================================

    def _open(
        self,
        operation: str,
        run_id: Any,
        parent_run_id: Any = None,
        conversation_context: Any = None,
    ) -> trace.Span:
        """Start and track a span for `run_id`, parented to its nearest ancestor.

        The parent is passed to the tracer explicitly rather than attached to
        the ambient context first: LangChain fires callbacks across tasks and
        threads, so the ambient context is not a reliable carrier and relying
        on it parented spans to whatever ran last.

        ``conversation_context`` applies only to a run with no traced ancestor,
        and puts it on an earlier turn's trace.
        """
        parent_context, parent_key = self._registry.resolve_parent(parent_run_id)
        span = self.tracer.start_span(
            name=operation,
            kind=SpanKind.CLIENT,
            context=parent_context or conversation_context,
        )
        span.set_attribute(AIAttributes.OPERATION_TYPE, _OPERATION_ATTRIBUTE[operation])
        self._registry.track(run_id, span, parent_key)
        return span

    def _begin(self, run_id: Any) -> bool:
        """Whether to record this run, claiming it if so."""
        if is_tracing_disabled():
            return False
        return self._registry.claim(run_id)

    def _succeed(self, run_id: Any) -> None:
        """Mark a run's span OK and end it."""
        if span := self._registry.span_for(run_id):
            span.set_status(Status(StatusCode.OK))
        self._registry.end(run_id)

    def _fail(self, run_id: Any, error: BaseException) -> bool:
        """Record an error on a run's span and end it.

        Returns whether there was a span, so a caller can clean up a run that
        was skipped rather than traced.
        """
        span = self._registry.span_for(run_id)
        if span is None:
            return False
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
        self._registry.end(run_id)
        return True

    def _add_content_event(self, run_id: Any, event: str, attribute: str, content: str) -> None:
        """Attach a truncated content event to a run's span, if it has one."""
        if span := self._registry.span_for(run_id):
            span.add_event(event, {attribute: content[:MAX_CONTENT_LENGTH]})

    # =====================================================================
    # LLM
    # =====================================================================

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Start span for chat model invocation."""
        if self._skip_llm(run_id) or not self._begin(run_id):
            return

        span = self._open(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
        set_llm_attributes(span, serialized, kwargs, request_type="chat")
        add_chat_prompt_event(span, messages)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Start span for non-chat LLM invocation."""
        if self._skip_llm(run_id) or not self._begin(run_id):
            return

        span = self._open(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
        set_llm_attributes(span, serialized, kwargs, request_type=serialized.get("_type", "llm"))

        if prompts:
            span.add_event(
                AIEvents.PROMPT,
                {
                    AIAttributes.PROMPT_ROLE: "user",
                    AIAttributes.PROMPT_CONTENT: prompts[0][:MAX_CONTENT_LENGTH],
                },
            )

    def on_llm_end(
        self, response: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """End LLM span with token counts and completion."""
        span = self._registry.span_for(run_id)
        if span is None:
            return
        try:
            extract_and_set_tokens(span, response)
        finally:
            self._succeed(run_id)

    def on_llm_error(
        self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """Handle LLM errors."""
        self._fail(run_id, error)

    def _skip_llm(self, run_id: Any) -> bool:
        """Whether an LLM span is unwanted here, before claiming the run."""
        if is_llm_observation_active():
            logger.debug("Skipping LLM span - @observe.llm() active for %s", run_id)
            return True
        return False

    # =====================================================================
    # Tools
    # =====================================================================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Start a tool span, or a handoff span for a delegation tool."""
        if not self._begin(run_id):
            return

        tool_name = serialized.get("name", "unknown")
        if tool_name.startswith(HANDOFF_TOOL_PREFIX):
            self._open_handoff(tool_name, run_id, parent_run_id)
            return

        span = self._open(AIOperationType.TOOL_INVOKE, run_id, parent_run_id)
        span.set_attribute(AIAttributes.TOOL_NAME, tool_name)
        span.set_attribute(AIAttributes.TOOL_TYPE, "function")
        span.add_event(
            AIEvents.TOOL_INPUT,
            {AIAttributes.TOOL_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
        )

    def _open_handoff(self, tool_name: str, run_id: Any, parent_run_id: Any) -> None:
        """Record one agent delegating to another."""
        span = self._open(AIOperationType.AGENT_HANDOFF, run_id, parent_run_id)
        if from_agent := self._registry.enclosing_agent(parent_run_id):
            span.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, from_agent)
        span.set_attribute(
            AIAttributes.AGENT_HANDOFF_TO,
            tool_name[len(HANDOFF_TOOL_PREFIX) :],
        )

    def on_tool_end(
        self, output: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """End tool span."""
        if self._registry.span_for(run_id) is None:
            return
        self._add_content_event(
            run_id,
            AIEvents.TOOL_OUTPUT,
            AIAttributes.TOOL_OUTPUT_CONTENT,
            extract_tool_output(output),
        )
        self._succeed(run_id)

    def on_tool_error(
        self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """Handle tool errors."""
        self._fail(run_id, error)

    # =====================================================================
    # Retrieval
    # =====================================================================

    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Start a retrieval span."""
        if not self._begin(run_id):
            return

        span = self._open(AIOperationType.RETRIEVAL, run_id, parent_run_id)
        span.set_attribute(
            AIAttributes.RETRIEVAL_BACKEND,
            extract_retriever_backend(serialized, metadata, kwargs),
        )
        span.add_event(
            AIEvents.RETRIEVAL_QUERY,
            {AIAttributes.PROMPT_CONTENT: str(query)[:MAX_CONTENT_LENGTH]},
        )

    def on_retriever_end(
        self, documents: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """End a retrieval span with the documents it returned."""
        span = self._registry.span_for(run_id)
        if span is None:
            return
        try:
            span.set_attribute(
                AIAttributes.RETRIEVAL_TOP_K, len(documents) if documents is not None else 0
            )
            span.add_event(
                AIEvents.RETRIEVAL_RESULTS,
                {AIAttributes.COMPLETION_CONTENT: summarize_documents(documents)},
            )
        finally:
            self._succeed(run_id)

    def on_retriever_error(
        self, error: BaseException, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """Handle retrieval errors."""
        self._fail(run_id, error)

    # =====================================================================
    # Chains and agents
    # =====================================================================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Start a span for this chain run if it is worth tracing."""
        if is_tracing_disabled() or self._registry.is_claimed(run_id):
            return

        agent_name = extract_agent_name(serialized, tags, metadata, kwargs)

        # Untraced runs are still recorded, so their children stay attached to
        # the nearest traced ancestor instead of becoming new roots.
        if not should_trace_chain(agent_name, tags, metadata):
            self._registry.skip(run_id, parent_run_id)
            return

        if not self._registry.claim(run_id):
            return
        self._registry.push_agent(run_id, agent_name)

        turn = resolve_turn(parent_run_id, metadata)
        span = self._open(
            AIOperationType.AGENT_INVOKE,
            run_id,
            parent_run_id,
            conversation_context=turn.parent_context if turn else None,
        )
        span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

        if turn:
            claim_turn_root(span, turn)

        if input_str := extract_agent_input(inputs):
            span.add_event(
                AIEvents.AGENT_INPUT,
                {AIAttributes.AGENT_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
            )

    def on_chain_end(
        self, outputs: Dict[str, Any], *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """End agent span."""
        if self._registry.span_for(run_id) is None:
            self._registry.forget_skipped(run_id)
            return

        if output_str := extract_agent_output(outputs):
            self._add_content_event(
                run_id, AIEvents.AGENT_OUTPUT, AIAttributes.AGENT_OUTPUT_CONTENT, output_str
            )
        self._succeed(run_id)
        self._registry.pop_agent(run_id)

    def on_chain_error(
        self, error: BaseException, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """Handle agent errors."""
        if not self._fail(run_id, error):
            self._registry.forget_skipped(run_id)
            return
        self._registry.pop_agent(run_id)


def create_langchain_callback():
    """Create a LangChain callback handler that records Rhesis spans."""
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except ImportError:
        from langchain.callbacks.base import BaseCallbackHandler

    # Built here rather than declared at module level because the base class
    # comes from an optional dependency. RhesisSpanRecorder leads the MRO so
    # its handlers win over BaseCallbackHandler's no-op defaults.
    handler_type = type(
        "RhesisLangChainCallback",
        (RhesisSpanRecorder, BaseCallbackHandler),
        {"__doc__": "OpenTelemetry callback handler for LangChain operations."},
    )
    return handler_type()

"""LangChain callback handler for OpenTelemetry tracing."""

import asyncio
import logging
import threading
from typing import Any, Dict, List

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.context import is_llm_observation_active, is_tracing_disabled
from rhesis.telemetry.schemas import AIOperationType

from .extractors import (
    MAX_CONTENT_LENGTH,
    extract_agent_input,
    extract_agent_name,
    extract_agent_output,
    extract_retriever_backend,
    extract_tool_output,
    should_trace_chain,
    summarize_documents,
)
from .llm_processing import (
    add_chat_prompt_event,
    extract_and_set_tokens,
    set_llm_attributes,
)

logger = logging.getLogger(__name__)

# An open span, the context token keeping it current, and the execution context
# that token belongs to.
SpanEntry = tuple[trace.Span, Any, tuple]

# Ceiling on in-flight bookkeeping. A run that never reports completion - a
# cancelled task, a killed worker - would otherwise hold its entry for the life
# of the process. Dicts iterate in insertion order, so the oldest goes first.
MAX_TRACKED_RUNS = 2048


def _execution_ident() -> tuple:
    """Identify the thread and asyncio task we are running on.

    A context token can only be detached from the context it was attached in.
    LangChain ends spans from other tasks and threads, where detaching logs an
    ERROR from inside OpenTelemetry that callers cannot catch, so compare this
    before attempting it.
    """
    try:
        task_id = id(asyncio.current_task())
    except RuntimeError:  # no running loop
        task_id = None
    return (threading.get_ident(), task_id)


def create_langchain_callback():
    """Create and return a LangChain callback handler for OpenTelemetry tracing."""
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except ImportError:
        from langchain.callbacks.base import BaseCallbackHandler

    class RhesisLangChainCallback(BaseCallbackHandler):
        """OpenTelemetry callback handler for LangChain operations."""

        def __init__(self):
            super().__init__()
            self.tracer = trace.get_tracer(__name__)
            self._spans: Dict[str, SpanEntry] = {}
            self._active_run_ids: set = set()
            # Runs we chose not to trace, mapped to the nearest ancestor that
            # *was* traced. Without this a skipped chain orphans everything
            # below it into its own trace.
            self._skipped_parents: Dict[str, str | None] = {}
            self._agent_run_ids: Dict[str, str] = {}  # run_id -> agent_name mapping
            # Innermost agent currently running, used as the handoff source.
            self._current_agent: str | None = None

        # =====================================================================
        # Span Management
        # =====================================================================

        def _resolve_parent_key(self, parent_run_id: Any) -> str | None:
            """Find the run_id whose span should parent a child of `parent_run_id`.

            Walks past runs that were skipped, so a child of an untraced LCEL
            step still lands under the graph node that contains it.
            """
            if not parent_run_id:
                return None
            key = str(parent_run_id)
            if key in self._spans:
                return key
            return self._skipped_parents.get(key)

        def _start_span(self, name: str, run_id: Any, parent_run_id: Any = None) -> SpanEntry:
            """Start a span parented to its run's nearest traced ancestor.

            The parent is passed explicitly rather than by attaching it to the
            ambient context first: LangChain fires callbacks across tasks and
            threads, so the ambient context is not a reliable carrier and
            relying on it produced spans parented to whatever ran last.
            """
            parent_context = None
            if parent_key := self._resolve_parent_key(parent_run_id):
                parent_span = self._spans[parent_key][0]
                parent_context = trace.set_span_in_context(parent_span)

            span = self.tracer.start_span(name=name, kind=SpanKind.CLIENT, context=parent_context)
            # Kept current so nested @observe() spans attach to this one.
            token = otel_context.attach(trace.set_span_in_context(span))
            return span, token, _execution_ident()

        def _skip_run(self, run_id: Any, parent_run_id: Any = None) -> None:
            """Record a run we are not tracing so its children keep their parent."""
            if len(self._skipped_parents) >= MAX_TRACKED_RUNS:
                self._skipped_parents.pop(next(iter(self._skipped_parents)), None)
            self._skipped_parents[str(run_id)] = self._resolve_parent_key(parent_run_id)

        def _track_span(self, run_id_str: str, entry: SpanEntry) -> None:
            """Record an open span, evicting the oldest if we are at the ceiling."""
            if len(self._spans) >= MAX_TRACKED_RUNS:
                self._abandon_oldest_span()
            self._spans[run_id_str] = entry

        def _abandon_oldest_span(self) -> None:
            """Close out the longest-running span so its slot can be reused.

            Ending it is better than dropping it: an unended span is never
            exported at all, so the work would vanish from the trace entirely.
            """
            oldest = next(iter(self._spans))
            span, _token, _ident = self._spans.pop(oldest)
            span.set_status(Status(StatusCode.ERROR, "run did not report completion"))
            span.end()
            self._active_run_ids.discard(oldest)
            self._agent_run_ids.pop(oldest, None)
            # Deliberately not detaching: this is the oldest token while newer
            # ones are still attached, so resetting it would discard their
            # context too. Newer spans release theirs normally.
            logger.debug("Abandoned span for run %s: tracking ceiling reached", oldest)

        def _end_span(self, run_id: Any) -> None:
            """End the span for a run and release its context token."""
            run_id_str = str(run_id)
            self._skipped_parents.pop(run_id_str, None)
            if run_id_str not in self._spans:
                return

            span, token, attached_in = self._spans.pop(run_id_str)
            span.end()
            self._active_run_ids.discard(run_id_str)

            # Only detach where the token is actually valid. Leaving it attached
            # elsewhere is harmless: the task is finishing and parenting no
            # longer reads the ambient context.
            if token and attached_in == _execution_ident():
                otel_context.detach(token)

        def _should_skip_llm(self, run_id: Any) -> bool:
            """Check if LLM span should be skipped (deduplication or tracing disabled)."""
            if is_tracing_disabled():
                return True
            if is_llm_observation_active():
                logger.debug(f"Skipping LLM span - @observe.llm() active for {run_id}")
                return True
            if str(run_id) in self._active_run_ids:
                logger.debug(f"Skipping duplicate LLM span for {run_id}")
                return True
            return False

        # =====================================================================
        # LLM Callbacks
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
            if self._should_skip_llm(run_id):
                return

            run_id_str = str(run_id)
            self._active_run_ids.add(run_id_str)

            span, token, ident = self._start_span(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
            set_llm_attributes(span, serialized, kwargs, request_type="chat")
            add_chat_prompt_event(span, messages)
            self._track_span(run_id_str, (span, token, ident))

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
            if self._should_skip_llm(run_id):
                return

            run_id_str = str(run_id)
            self._active_run_ids.add(run_id_str)

            span, token, ident = self._start_span(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
            set_llm_attributes(
                span, serialized, kwargs, request_type=serialized.get("_type", "llm")
            )

            if prompts:
                span.add_event(
                    AIEvents.PROMPT,
                    {
                        AIAttributes.PROMPT_ROLE: "user",
                        AIAttributes.PROMPT_CONTENT: prompts[0][:MAX_CONTENT_LENGTH],
                    },
                )
            self._track_span(run_id_str, (span, token, ident))

        def on_llm_end(
            self, response: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End LLM span with token counts and completion."""
            span_data = self._spans.get(str(run_id))
            if not span_data:
                return

            span, _, _ = span_data
            try:
                extract_and_set_tokens(span, response)
                span.set_status(Status(StatusCode.OK))
            finally:
                self._end_span(run_id)

        def on_llm_error(
            self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """Handle LLM errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =====================================================================
        # Tool Callbacks
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
            """Start tool span or handoff span."""
            if is_tracing_disabled():
                return

            run_id_str = str(run_id)
            if run_id_str in self._active_run_ids:
                return

            self._active_run_ids.add(run_id_str)
            tool_name = serialized.get("name", "unknown")

            # Detect handoff tools (transfer_to_* pattern)
            if tool_name.startswith("transfer_to_"):
                # Extract target agent from tool name
                target_agent = tool_name.replace("transfer_to_", "")

                span, token, ident = self._start_span(
                    AIOperationType.AGENT_HANDOFF, run_id, parent_run_id
                )

                span.set_attribute(
                    AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_HANDOFF
                )
                if self._current_agent:
                    span.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, self._current_agent)
                span.set_attribute(AIAttributes.AGENT_HANDOFF_TO, target_agent)
            else:
                # Regular tool invocation
                span, token, ident = self._start_span(
                    AIOperationType.TOOL_INVOKE, run_id, parent_run_id
                )

                span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
                span.set_attribute(AIAttributes.TOOL_NAME, tool_name)
                span.set_attribute(AIAttributes.TOOL_TYPE, "function")
                span.add_event(
                    AIEvents.TOOL_INPUT,
                    {AIAttributes.TOOL_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

            self._track_span(run_id_str, (span, token, ident))

        def on_tool_end(
            self, output: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End tool span."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                output_str = extract_tool_output(output)
                span_data[0].add_event(
                    AIEvents.TOOL_OUTPUT,
                    {AIAttributes.TOOL_OUTPUT_CONTENT: output_str[:MAX_CONTENT_LENGTH]},
                )
                span_data[0].set_status(Status(StatusCode.OK))
                self._end_span(run_id)

        def on_tool_error(
            self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """Handle tool errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =====================================================================
        # Retriever Callbacks
        # =====================================================================

        def on_retriever_start(
            self,
            serialized: Dict[str, Any],
            query: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            tags: List[str] | None = None,
            metadata: Dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> None:
            """Start a retrieval span."""
            if is_tracing_disabled():
                return

            run_id_str = str(run_id)
            if run_id_str in self._active_run_ids:
                return

            self._active_run_ids.add(run_id_str)

            span, token, ident = self._start_span(AIOperationType.RETRIEVAL, run_id, parent_run_id)
            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_RETRIEVAL)
            span.set_attribute(
                AIAttributes.RETRIEVAL_BACKEND,
                extract_retriever_backend(serialized, metadata, kwargs),
            )
            span.add_event(
                AIEvents.RETRIEVAL_QUERY,
                {AIAttributes.PROMPT_CONTENT: str(query)[:MAX_CONTENT_LENGTH]},
            )
            self._track_span(run_id_str, (span, token, ident))

        def on_retriever_end(
            self, documents: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End a retrieval span with the documents it returned."""
            span_data = self._spans.get(str(run_id))
            if not span_data:
                return

            span = span_data[0]
            try:
                count = len(documents) if documents is not None else 0
                span.set_attribute(AIAttributes.RETRIEVAL_TOP_K, count)
                span.add_event(
                    AIEvents.RETRIEVAL_RESULTS,
                    {AIAttributes.COMPLETION_CONTENT: summarize_documents(documents)},
                )
                span.set_status(Status(StatusCode.OK))
            finally:
                self._end_span(run_id)

        def on_retriever_error(
            self, error: BaseException, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """Handle retrieval errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =====================================================================
        # Agent Callbacks (for multi-agent systems)
        # =====================================================================

        def on_chain_start(
            self,
            serialized: Dict[str, Any],
            inputs: Dict[str, Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            tags: List[str] | None = None,
            metadata: Dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> None:
            """Start a span for this chain run if it is worth tracing."""
            if is_tracing_disabled():
                return

            run_id_str = str(run_id)

            # Skip if we've already processed this run
            if run_id_str in self._active_run_ids:
                return

            agent_name = extract_agent_name(serialized, tags, metadata, kwargs)

            # Untraced runs are still recorded, so their children stay attached
            # to the nearest traced ancestor instead of becoming new roots.
            if not should_trace_chain(agent_name, tags, metadata):
                self._skip_run(run_id, parent_run_id)
                return

            self._active_run_ids.add(run_id_str)
            self._agent_run_ids[run_id_str] = agent_name
            self._current_agent = agent_name

            span, token, ident = self._start_span(
                AIOperationType.AGENT_INVOKE, run_id, parent_run_id
            )

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
            span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

            # Capture agent input
            input_str = extract_agent_input(inputs)
            if input_str:
                span.add_event(
                    AIEvents.AGENT_INPUT,
                    {AIAttributes.AGENT_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

            self._track_span(run_id_str, (span, token, ident))

        def on_chain_end(
            self,
            outputs: Dict[str, Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """End agent span."""
            run_id_str = str(run_id)
            span_data = self._spans.get(run_id_str)
            if not span_data:
                # Untraced run: drop its parent link now that it is over.
                self._skipped_parents.pop(run_id_str, None)
                return

            # Capture agent output
            output_str = extract_agent_output(outputs)
            if output_str:
                span_data[0].add_event(
                    AIEvents.AGENT_OUTPUT,
                    {AIAttributes.AGENT_OUTPUT_CONTENT: output_str[:MAX_CONTENT_LENGTH]},
                )
            span_data[0].set_status(Status(StatusCode.OK))
            self._end_span(run_id)
            self._release_agent(run_id_str)

        def on_chain_error(
            self,
            error: BaseException,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Handle agent errors."""
            run_id_str = str(run_id)
            span_data = self._spans.get(run_id_str)
            if not span_data:
                self._skipped_parents.pop(run_id_str, None)
                return

            span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
            span_data[0].record_exception(error)
            self._end_span(run_id)
            self._release_agent(run_id_str)

        # =====================================================================
        # Helper Methods
        # =====================================================================

        def _release_agent(self, run_id_str: str) -> None:
            """Drop bookkeeping for an agent span that has ended."""
            if run_id_str in self._agent_run_ids:
                agent_name = self._agent_run_ids.pop(run_id_str)
                if self._current_agent == agent_name:
                    self._current_agent = None

    return RhesisLangChainCallback()

"""LangChain callback handler for OpenTelemetry tracing."""

import asyncio
import logging
import threading
from typing import Any, Dict, List, NamedTuple

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.telemetry.attributes import AIAttributes, AIEvents
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.context import (
    get_conversation_trace_id,
    get_root_trace_id,
    is_llm_observation_active,
    is_tracing_disabled,
)
from rhesis.telemetry.conversation import (
    anchor_conversation,
    build_conversation_parent_context,
    get_conversation_anchor,
)
from rhesis.telemetry.schemas import AIOperationType

from .extractors import (
    MAX_CONTENT_LENGTH,
    extract_agent_input,
    extract_agent_name,
    extract_agent_output,
    extract_conversation_id,
    extract_retriever_backend,
    extract_tool_output,
    is_langgraph_root,
    should_trace_chain,
    summarize_documents,
)
from .llm_processing import (
    add_chat_prompt_event,
    extract_and_set_tokens,
    set_llm_attributes,
)

logger = logging.getLogger(__name__)

_CONVERSATION_ATTRS = ConversationContext.SpanAttributes

# An open span, the context token keeping it current, the execution context
# that token belongs to, and the run whose span parents it.
SpanEntry = tuple[trace.Span, Any, tuple, "str | None"]

# How far to walk a run's ancestors looking for the agent it runs inside.
# Deeper than any real graph nests; a cap so the walk cannot spin.
MAX_ANCESTRY_DEPTH = 64


class _AgentRun(NamedTuple):
    """An open agent span: its name, and the execution it was opened on."""

    name: str
    ident: tuple


class _TurnClaim(NamedTuple):
    """A run that opens a conversation turn, and the trace to open it on.

    ``parent_context`` is a synthetic parent onto an earlier turn's trace, or
    None for the first turn of a conversation.
    """

    conversation_id: str
    parent_context: Any


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
            self._agent_run_ids: Dict[str, _AgentRun] = {}
            # Agents currently on the stack, per thread/task. Tools reached
            # through the patched BaseTool.invoke arrive as root runs with no
            # parent_run_id, so ancestry alone cannot say which agent called
            # them; the execution they run on can. Keyed per execution rather
            # than held in one field because LangGraph runs parallel nodes on
            # separate threads, which a single field cannot represent.
            self._agent_stacks: Dict[tuple, List[str]] = {}
            # One handler instance serves the whole process, and LangGraph runs
            # parallel nodes on separate threads, so every read-then-write over
            # the maps above has to be atomic. Reentrant because the helpers
            # below call each other.
            self._lock = threading.RLock()

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
            with self._lock:
                key = str(parent_run_id)
                if key in self._spans:
                    return key
                return self._skipped_parents.get(key)

        def _enclosing_agent(self, parent_run_id: Any) -> str | None:
            """Name the agent this run is executing inside, if any.

            Ancestry first, since it is exact. Runs that arrive without a
            parent - anything reached through the patched ``BaseTool.invoke`` -
            fall back to the innermost agent on this thread or task.
            """
            with self._lock:
                if agent_name := self._agent_from_ancestry(parent_run_id):
                    return agent_name
                stack = self._agent_stacks.get(_execution_ident())
                return stack[-1] if stack else None

        def _agent_from_ancestry(self, parent_run_id: Any) -> str | None:
            """Walk a run's parents for the nearest one that is an agent."""
            key = self._resolve_parent_key(parent_run_id)
            # Bounded rather than `while key`: a hot path must not be able to
            # spin, whatever shape the run tree arrives in.
            for _ in range(MAX_ANCESTRY_DEPTH):
                if key is None:
                    return None
                if agent := self._agent_run_ids.get(key):
                    return agent.name
                entry = self._spans.get(key)
                key = entry[3] if entry else None
            return None

        def _push_agent(self, run_id_str: str, agent_name: str) -> None:
            """Record an agent as running, and as innermost on this execution."""
            ident = _execution_ident()
            with self._lock:
                self._agent_run_ids[run_id_str] = _AgentRun(agent_name, ident)
                self._agent_stacks.setdefault(ident, []).append(agent_name)

        def _pop_agent(self, run_id_str: str) -> None:
            """Drop an agent that has ended, and unstack it."""
            with self._lock:
                agent = self._agent_run_ids.pop(run_id_str, None)
                if agent is None:
                    return
                stack = self._agent_stacks.get(agent.ident)
                if not stack:
                    return
                # Remove this agent specifically: nested agents on one
                # execution need not end in the order they started.
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i] == agent.name:
                        del stack[i]
                        break
                if not stack:
                    # Or the map grows one entry per thread ever used.
                    self._agent_stacks.pop(agent.ident, None)

        def _start_span(
            self,
            name: str,
            run_id: Any,
            parent_run_id: Any = None,
            conversation_context: Any = None,
        ) -> SpanEntry:
            """Start a span parented to its run's nearest traced ancestor.

            The parent is passed explicitly rather than by attaching it to the
            ambient context first: LangChain fires callbacks across tasks and
            threads, so the ambient context is not a reliable carrier and
            relying on it produced spans parented to whatever ran last.

            ``conversation_context`` only applies to a run with no traced
            ancestor, and puts it on an earlier turn's trace.
            """
            parent_context = conversation_context
            parent_key = None
            with self._lock:
                # Resolved and read together: the parent's span can be ended by
                # another thread between the two.
                if resolved := self._resolve_parent_key(parent_run_id):
                    if entry := self._spans.get(resolved):
                        parent_key = resolved
                        parent_context = trace.set_span_in_context(entry[0])

            span = self.tracer.start_span(name=name, kind=SpanKind.CLIENT, context=parent_context)
            # Kept current so nested @observe() spans attach to this one.
            token = otel_context.attach(trace.set_span_in_context(span))
            return span, token, _execution_ident(), parent_key

        def _skip_run(self, run_id: Any, parent_run_id: Any = None) -> None:
            """Record a run we are not tracing so its children keep their parent."""
            parent_key = self._resolve_parent_key(parent_run_id)
            with self._lock:
                if len(self._skipped_parents) >= MAX_TRACKED_RUNS:
                    self._skipped_parents.pop(next(iter(self._skipped_parents), None), None)
                self._skipped_parents[str(run_id)] = parent_key

        def _track_span(self, run_id_str: str, entry: SpanEntry) -> None:
            """Record an open span, evicting the oldest if we are at the ceiling."""
            with self._lock:
                if len(self._spans) >= MAX_TRACKED_RUNS:
                    self._abandon_oldest_span()
                self._spans[run_id_str] = entry

        def _abandon_oldest_span(self) -> None:
            """Close out the longest-running span so its slot can be reused.

            Ending it is better than dropping it: an unended span is never
            exported at all, so the work would vanish from the trace entirely.
            """
            with self._lock:
                oldest = next(iter(self._spans), None)
                if oldest is None:
                    return
                entry = self._spans.pop(oldest, None)
                self._active_run_ids.discard(oldest)
                # Unstack it too, or an abandoned agent stays innermost for
                # every later tool on that execution.
                self._pop_agent(oldest)

            if entry is None:
                return

            entry[0].set_status(Status(StatusCode.ERROR, "run did not report completion"))
            entry[0].end()
            # Deliberately not detaching: this is the oldest token while newer
            # ones are still attached, so resetting it would discard their
            # context too. Newer spans release theirs normally.
            logger.debug("Abandoned span for run %s: tracking ceiling reached", oldest)

        def _end_span(self, run_id: Any) -> None:
            """End the span for a run and release its context token."""
            run_id_str = str(run_id)
            with self._lock:
                self._skipped_parents.pop(run_id_str, None)
                entry = self._spans.pop(run_id_str, None)
                self._active_run_ids.discard(run_id_str)
            if entry is None:
                return

            span, token, attached_in, _parent_key = entry
            span.end()

            # Only detach where the token is actually valid. Leaving it attached
            # elsewhere is harmless: the task is finishing and parenting no
            # longer reads the ambient context.
            if token and attached_in == _execution_ident():
                otel_context.detach(token)

        # =====================================================================
        # Conversation Turns
        # =====================================================================

        def _resolve_turn(self, parent_run_id: Any, metadata: Dict | None) -> _TurnClaim | None:
            """Decide whether this run opens a conversation turn, and on which trace.

            Only a LangGraph root qualifies, and only when nothing else already
            owns the turn. Two spans claiming ``is_turn_root`` in one exchange
            makes the exporter strip the real parent of one of them, detaching
            its subtree into a phantom turn - so an enclosing ``conversation_turn``,
            ``@endpoint`` or ``@observe`` stands this down, as does any ambient
            span this run would nest under.
            """
            if parent_run_id or not is_langgraph_root(metadata):
                return None

            if get_root_trace_id() is not None or get_conversation_trace_id() is not None:
                return None

            if trace.get_current_span().get_span_context().is_valid:
                return None

            conversation_id = extract_conversation_id(metadata)
            if not conversation_id:
                return None

            anchor = get_conversation_anchor(conversation_id)
            parent_context = build_conversation_parent_context(anchor) if anchor else None
            return _TurnClaim(conversation_id, parent_context)

        def _claim_turn_root(self, span: trace.Span, claim: _TurnClaim) -> None:
            """Mark a span as the root of a conversation turn.

            The exporter reads these two attributes to give every span sharing
            this trace the same conversation id.
            """
            span.set_attribute(_CONVERSATION_ATTRS.IS_TURN_ROOT, True)
            span.set_attribute(_CONVERSATION_ATTRS.CONVERSATION_ID, claim.conversation_id)

            span_context = span.get_span_context()
            if span_context.is_valid:
                # First turn of this conversation anchors it; later turns were
                # already pulled onto that trace by the parent context above.
                anchor_conversation(claim.conversation_id, format(span_context.trace_id, "032x"))

        def _claim_run(self, run_id: Any) -> bool:
            """Take ownership of a run, or report it as already claimed.

            Checking and claiming together, so two threads cannot both open a
            span for the same run.
            """
            run_id_str = str(run_id)
            with self._lock:
                if run_id_str in self._active_run_ids:
                    return False
                self._active_run_ids.add(run_id_str)
                return True

        def _is_claimed(self, run_id_str: str) -> bool:
            """Cheap pre-filter for runs already being traced.

            Not atomic with the claim that follows it, and does not need to be:
            it only avoids work, and :meth:`_claim_run` settles who wins.
            """
            return run_id_str in self._active_run_ids

        def _should_skip_llm(self, run_id: Any) -> bool:
            """Whether an LLM span is unwanted here, before claiming the run."""
            if is_tracing_disabled():
                return True
            if is_llm_observation_active():
                logger.debug(f"Skipping LLM span - @observe.llm() active for {run_id}")
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
            if self._should_skip_llm(run_id) or not self._claim_run(run_id):
                return

            run_id_str = str(run_id)

            entry = self._start_span(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
            span = entry[0]
            set_llm_attributes(span, serialized, kwargs, request_type="chat")
            add_chat_prompt_event(span, messages)
            self._track_span(run_id_str, entry)

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
            if self._should_skip_llm(run_id) or not self._claim_run(run_id):
                return

            run_id_str = str(run_id)

            entry = self._start_span(AIOperationType.LLM_INVOKE, run_id, parent_run_id)
            span = entry[0]
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
            self._track_span(run_id_str, entry)

        def on_llm_end(
            self, response: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End LLM span with token counts and completion."""
            span_data = self._spans.get(str(run_id))
            if not span_data:
                return

            span = span_data[0]
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
            if not self._claim_run(run_id):
                return
            tool_name = serialized.get("name", "unknown")

            # Detect handoff tools (transfer_to_* pattern)
            if tool_name.startswith("transfer_to_"):
                # Extract target agent from tool name
                target_agent = tool_name.replace("transfer_to_", "")

                entry = self._start_span(AIOperationType.AGENT_HANDOFF, run_id, parent_run_id)
                span = entry[0]

                span.set_attribute(
                    AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_HANDOFF
                )
                if from_agent := self._enclosing_agent(parent_run_id):
                    span.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, from_agent)
                span.set_attribute(AIAttributes.AGENT_HANDOFF_TO, target_agent)
            else:
                # Regular tool invocation
                entry = self._start_span(AIOperationType.TOOL_INVOKE, run_id, parent_run_id)
                span = entry[0]

                span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
                span.set_attribute(AIAttributes.TOOL_NAME, tool_name)
                span.set_attribute(AIAttributes.TOOL_TYPE, "function")
                span.add_event(
                    AIEvents.TOOL_INPUT,
                    {AIAttributes.TOOL_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

            self._track_span(run_id_str, entry)

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
            if not self._claim_run(run_id):
                return

            entry = self._start_span(AIOperationType.RETRIEVAL, run_id, parent_run_id)
            span = entry[0]
            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_RETRIEVAL)
            span.set_attribute(
                AIAttributes.RETRIEVAL_BACKEND,
                extract_retriever_backend(serialized, metadata, kwargs),
            )
            span.add_event(
                AIEvents.RETRIEVAL_QUERY,
                {AIAttributes.PROMPT_CONTENT: str(query)[:MAX_CONTENT_LENGTH]},
            )
            self._track_span(run_id_str, entry)

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

            # Cheap pre-filter; the claim below decides it for real.
            if self._is_claimed(run_id_str):
                return

            agent_name = extract_agent_name(serialized, tags, metadata, kwargs)

            # Untraced runs are still recorded, so their children stay attached
            # to the nearest traced ancestor instead of becoming new roots.
            if not should_trace_chain(agent_name, tags, metadata):
                self._skip_run(run_id, parent_run_id)
                return

            if not self._claim_run(run_id):
                return
            self._push_agent(run_id_str, agent_name)

            conversation = self._resolve_turn(parent_run_id, metadata)

            entry = self._start_span(
                AIOperationType.AGENT_INVOKE,
                run_id,
                parent_run_id,
                conversation_context=conversation.parent_context if conversation else None,
            )
            span = entry[0]

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
            span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

            if conversation:
                self._claim_turn_root(span, conversation)

            # Capture agent input
            input_str = extract_agent_input(inputs)
            if input_str:
                span.add_event(
                    AIEvents.AGENT_INPUT,
                    {AIAttributes.AGENT_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

            self._track_span(run_id_str, entry)

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
            self._pop_agent(run_id_str)

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
            self._pop_agent(run_id_str)

        # =====================================================================
        # Helper Methods
        # =====================================================================

    return RhesisLangChainCallback()

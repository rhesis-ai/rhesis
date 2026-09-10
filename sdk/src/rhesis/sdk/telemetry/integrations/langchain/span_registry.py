"""Bookkeeping for the spans a LangChain run tree is producing.

LangChain reports work as a stream of (run_id, parent_run_id) events rather
than a call stack, so something has to remember which run owns which span,
which runs were skipped, and which agent a run is executing inside. This module
owns that state and nothing about OpenTelemetry semantics: the callback decides
what a span means, the registry decides where it belongs and when it ends.

One handler instance serves the whole process once it is registered through
LangChain's configure hook, and LangGraph runs parallel nodes on separate
threads, so every read-then-write here is taken under one reentrant lock.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, List, NamedTuple, Optional

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

# Ceiling on in-flight bookkeeping. A run that never reports completion - a
# cancelled task, a killed worker - would otherwise hold its entry for the life
# of the process. Dicts iterate in insertion order, so the oldest goes first.
MAX_TRACKED_RUNS = 2048

# How far to walk a run's ancestors looking for the agent it runs inside.
# Deeper than any real graph nests; a cap so the walk cannot spin.
MAX_ANCESTRY_DEPTH = 64


def execution_ident() -> tuple:
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


class TrackedSpan(NamedTuple):
    """An open span and what is needed to close it correctly."""

    span: trace.Span
    token: Any
    """Context token keeping the span current, so nested @observe() spans attach."""
    attached_in: tuple
    """The execution that attached the token, and the only one that may detach it."""
    parent_key: Optional[str]
    """The run whose span parents this one, for walking ancestry."""


class _AgentRun(NamedTuple):
    """An open agent span: its name, and the execution it was opened on."""

    name: str
    ident: tuple


class SpanRegistry:
    """Tracks the open spans of a run tree, and where each run belongs."""

    def __init__(self) -> None:
        self._spans: Dict[str, TrackedSpan] = {}
        self._claimed: set = set()
        # Runs we chose not to trace, mapped to the nearest ancestor that *was*
        # traced. Without this a skipped chain orphans everything below it into
        # its own trace.
        self._skipped_parents: Dict[str, Optional[str]] = {}
        self._agent_runs: Dict[str, _AgentRun] = {}
        # Agents currently on the stack, per thread/task. Tools reached through
        # the patched BaseTool.invoke arrive as root runs with no
        # parent_run_id, so ancestry alone cannot say which agent called them;
        # the execution they run on can. Keyed per execution because LangGraph
        # runs parallel nodes on separate threads, which one field cannot
        # represent.
        self._agent_stacks: Dict[tuple, List[str]] = {}
        self._lock = threading.RLock()

    # -- claiming ---------------------------------------------------------

    def claim(self, run_id: Any) -> bool:
        """Take ownership of a run, or report it as already claimed.

        Checking and claiming together, so two threads cannot both open a span
        for the same run.
        """
        run_id_str = str(run_id)
        with self._lock:
            if run_id_str in self._claimed:
                return False
            self._claimed.add(run_id_str)
            return True

    def is_claimed(self, run_id: Any) -> bool:
        """Cheap pre-filter for runs already being traced.

        Not atomic with the claim that may follow, and does not need to be: it
        only avoids work, and :meth:`claim` settles who wins.
        """
        return str(run_id) in self._claimed

    # -- parenting --------------------------------------------------------

    def resolve_parent(self, parent_run_id: Any) -> tuple[Optional[trace.Context], Optional[str]]:
        """Return the context and run key that should parent a child of `parent_run_id`.

        Resolved and read under one lock: the parent's span can be ended by
        another thread between finding its key and reading its span.
        """
        if not parent_run_id:
            return None, None
        with self._lock:
            key = self._parent_key(parent_run_id)
            if key is None:
                return None, None
            tracked = self._spans.get(key)
            if tracked is None:
                return None, None
            return trace.set_span_in_context(tracked.span), key

    def _parent_key(self, parent_run_id: Any) -> Optional[str]:
        """Find the run whose span should parent a child of `parent_run_id`.

        Walks past runs that were skipped, so a child of an untraced LCEL step
        still lands under the graph node that contains it.
        """
        if not parent_run_id:
            return None
        key = str(parent_run_id)
        if key in self._spans:
            return key
        return self._skipped_parents.get(key)

    def skip(self, run_id: Any, parent_run_id: Any = None) -> None:
        """Record a run we are not tracing so its children keep their parent."""
        with self._lock:
            parent_key = self._parent_key(parent_run_id)
            if len(self._skipped_parents) >= MAX_TRACKED_RUNS:
                self._skipped_parents.pop(next(iter(self._skipped_parents), None), None)
            self._skipped_parents[str(run_id)] = parent_key

    def forget_skipped(self, run_id: Any) -> None:
        """Drop a skipped run's parent link now that the run is over."""
        with self._lock:
            self._skipped_parents.pop(str(run_id), None)

    # -- span lifecycle ---------------------------------------------------

    def track(self, run_id: Any, span: trace.Span, parent_key: Optional[str]) -> None:
        """Record an open span, evicting the oldest if we are at the ceiling.

        Also makes the span current, so nested ``@observe()`` spans attach to it.
        """
        token = otel_context.attach(trace.set_span_in_context(span))
        tracked = TrackedSpan(span, token, execution_ident(), parent_key)
        with self._lock:
            if len(self._spans) >= MAX_TRACKED_RUNS:
                self._abandon_oldest()
            self._spans[str(run_id)] = tracked

    def span_for(self, run_id: Any) -> Optional[trace.Span]:
        """The open span of a run, if it has one."""
        tracked = self._spans.get(str(run_id))
        return tracked.span if tracked else None

    def end(self, run_id: Any) -> None:
        """End the span for a run and release its context token."""
        run_id_str = str(run_id)
        with self._lock:
            self._skipped_parents.pop(run_id_str, None)
            tracked = self._spans.pop(run_id_str, None)
            self._claimed.discard(run_id_str)
        if tracked is None:
            return

        tracked.span.end()
        # Only detach where the token is actually valid. Leaving it attached
        # elsewhere is harmless: the execution is finishing and parenting no
        # longer reads the ambient context.
        if tracked.token and tracked.attached_in == execution_ident():
            otel_context.detach(tracked.token)

    def _abandon_oldest(self) -> None:
        """Close out the longest-running span so its slot can be reused.

        Ending it is better than dropping it: an unended span is never exported
        at all, so the work would vanish from the trace entirely.
        """
        oldest = next(iter(self._spans), None)
        if oldest is None:
            return
        tracked = self._spans.pop(oldest, None)
        self._claimed.discard(oldest)
        # Unstack it too, or an abandoned agent stays innermost for every later
        # tool on that execution.
        self.pop_agent(oldest)
        if tracked is None:
            return

        tracked.span.set_status(Status(StatusCode.ERROR, "run did not report completion"))
        tracked.span.end()
        # Deliberately not detaching: this is the oldest token while newer ones
        # are still attached, so resetting it would discard their context too.
        # Newer spans release theirs normally.
        logger.debug("Abandoned span for run %s: tracking ceiling reached", oldest)

    # -- agents -----------------------------------------------------------

    def push_agent(self, run_id: Any, agent_name: str) -> None:
        """Record an agent as running, and as innermost on this execution."""
        ident = execution_ident()
        with self._lock:
            self._agent_runs[str(run_id)] = _AgentRun(agent_name, ident)
            self._agent_stacks.setdefault(ident, []).append(agent_name)

    def pop_agent(self, run_id: Any) -> None:
        """Drop an agent that has ended, and unstack it."""
        with self._lock:
            agent = self._agent_runs.pop(str(run_id), None)
            if agent is None:
                return
            stack = self._agent_stacks.get(agent.ident)
            if not stack:
                return
            # Remove this agent specifically: nested agents on one execution
            # need not end in the order they started.
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] == agent.name:
                    del stack[i]
                    break
            if not stack:
                # Or the map grows one entry per thread ever used.
                self._agent_stacks.pop(agent.ident, None)

    def enclosing_agent(self, parent_run_id: Any) -> Optional[str]:
        """Name the agent a run is executing inside, if any.

        Ancestry first, since it is exact. Runs that arrive without a parent -
        anything reached through the patched ``BaseTool.invoke`` - fall back to
        the innermost agent on this thread or task.
        """
        with self._lock:
            if agent_name := self._agent_from_ancestry(parent_run_id):
                return agent_name
            stack = self._agent_stacks.get(execution_ident())
            return stack[-1] if stack else None

    def _agent_from_ancestry(self, parent_run_id: Any) -> Optional[str]:
        """Walk a run's parents for the nearest one that is an agent."""
        key = self._parent_key(parent_run_id)
        # Bounded rather than `while key`: a hot path must not be able to spin,
        # whatever shape the run tree arrives in.
        for _ in range(MAX_ANCESTRY_DEPTH):
            if key is None:
                return None
            if agent := self._agent_runs.get(key):
                return agent.name
            tracked = self._spans.get(key)
            key = tracked.parent_key if tracked else None
        return None

"""What a metric is scored on, passed through the strategies as one object."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.arguments import judged_input_output
from rhesis.sdk.metrics.expectations import Expectations

logger = logging.getLogger(__name__)

TraceLoader = Callable[[], Optional[Trace]]

_CONVERSATION_INPUT = "rhesis.conversation.input"


def _one_turn(trace: Trace) -> Trace:
    """The trace of the response's own turn. The turns of a conversation share a trace id, so a
    stored trace can hold others; the first turn is the one the response's output came from."""
    turns = [root for root in trace.root_spans if root.attributes.get(_CONVERSATION_INPUT)]
    if len(turns) > 1:
        others = {id(root) for root in turns[1:]}
        trace.root_spans = [root for root in trace.root_spans if id(root) not in others]
    return trace


@dataclass
class ResponseTrace:
    """The trace of one endpoint response, read on first use.

    The stored spans with the live response on their root, or one built from the response when
    nothing is stored. ``loader`` reads the stored trace the first time a metric asks for it;
    the native judges do, to show the trace's context, tool calls and metadata. Metrics run in
    parallel threads; the lock keeps it to one read.
    """

    input: str
    output: str
    context: Optional[List[str]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    loader: Optional[TraceLoader] = None

    _trace: Optional[Trace] = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def load(self) -> Trace:
        from rhesis.backend.app.services.telemetry.evaluation_trace import (
            trace_from_response,
            with_live_values,
        )

        with self._lock:
            if self._trace is None:
                stored = None
                if self.loader is not None:
                    try:
                        stored = self.loader()
                    except Exception:
                        logger.warning("Could not read the trace for evaluation", exc_info=True)
                parts = {
                    "context": self.context,
                    "tool_calls": self.tool_calls,
                    "metadata": self.metadata,
                }
                if stored is not None and stored.root_spans:
                    self._trace = with_live_values(
                        _one_turn(stored), self.input, self.output, **parts
                    )
                else:
                    if self.loader is not None:
                        logger.info("No stored trace to evaluate; building one from the response")
                    self._trace = trace_from_response(self.input, self.output, **parts)
            return self._trace


@dataclass
class EvaluationInputs:
    """What happened (the trace) and what should have (the expectations). Each metric
    receives only the names its own signature declares (see ``build_metric_evaluate_params``).

    ``trace`` is a Trace in hand (a conversation, a production trace) or the ``ResponseTrace``
    of one response, which reads the stored spans only if a metric asks for the trace.
    """

    trace: Union[Trace, ResponseTrace]
    expectations: Optional[Expectations] = None

    _judged: Optional[Tuple[str, str]] = field(default=None, init=False, repr=False)
    _trace_json: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def load_trace(self) -> Trace:
        """The trace, read from storage the first time a response's trace is asked for."""
        return self.trace.load() if isinstance(self.trace, ResponseTrace) else self.trace

    def _input_output(self) -> Tuple[str, str]:
        # A response's own input and output need no read of the stored trace.
        if isinstance(self.trace, ResponseTrace):
            return self.trace.input, self.trace.output
        if self._judged is None:
            self._judged = judged_input_output(self.trace, self.expectations)
        return self._judged

    @property
    def input_text(self) -> str:
        """The input of what metrics judge: a turn's input, or a conversation's goal."""
        return self._input_output()[0]

    @property
    def output_text(self) -> str:
        """The output of what metrics judge: a turn's output, or a conversation's transcript."""
        return self._input_output()[1]

    def trace_json(self) -> Dict[str, Any]:
        """``load_trace()`` as JSON, for SDK metrics. Built once however many ask."""
        trace = self.load_trace()
        with self._lock:
            if self._trace_json is None:
                self._trace_json = trace.model_dump(mode="json", exclude_none=True)
            return self._trace_json

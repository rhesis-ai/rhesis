"""What a metric is scored on, passed through the strategies as one object."""

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from rhesis.sdk.entities.trace import Trace

logger = logging.getLogger(__name__)

TraceLoader = Callable[[], Optional["Trace"]]


@dataclass
class EvaluationInputs:
    """Everything a metric may ask for. Each metric receives only the names its own
    signature declares (see ``build_metric_evaluate_params``).

    ``trace_loader`` reads the stored trace on first use, so evaluations whose metrics never
    ask for ``trace`` never load one.
    """

    input_text: str
    output_text: str
    expected_output: str
    context: List[str]
    conversation_history: Any = None
    metadata: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    instructions: Optional[str] = None
    contract: Optional[Dict[str, Any]] = None
    trace_loader: Optional[TraceLoader] = None

    _trace: Optional["Trace"] = field(default=None, init=False, repr=False)
    _trace_json: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _trace_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def load_trace(self) -> "Trace":
        """The trace of what was evaluated: the stored one with the live input and output on
        its root, or one built from the request and response when nothing is stored.

        Metrics run in parallel threads; the lock keeps it to one read.
        """
        from rhesis.backend.app.services.telemetry.evaluation_trace import (
            trace_from_response,
            with_live_values,
        )

        with self._trace_lock:
            if self._trace is None:
                stored = None
                if self.trace_loader is not None:
                    try:
                        stored = self.trace_loader()
                    except Exception:
                        logger.warning("Could not read the trace for evaluation", exc_info=True)
                if stored is not None and stored.root_spans:
                    self._trace = with_live_values(
                        stored,
                        self.input_text,
                        self.output_text,
                        context=self.context,
                        tool_calls=self.tool_calls,
                        metadata=self.metadata,
                    )
                else:
                    if self.trace_loader is not None:
                        logger.info("No stored trace to evaluate; building one from the response")
                    self._trace = trace_from_response(
                        self.input_text,
                        self.output_text,
                        context=self.context,
                        tool_calls=self.tool_calls,
                        metadata=self.metadata,
                    )
            return self._trace

    def trace_json(self) -> Dict[str, Any]:
        """``load_trace()`` as JSON, for SDK metrics. Built once however many ask."""
        trace = self.load_trace()
        with self._trace_lock:
            if self._trace_json is None:
                self._trace_json = trace.model_dump(mode="json", exclude_none=True)
            return self._trace_json

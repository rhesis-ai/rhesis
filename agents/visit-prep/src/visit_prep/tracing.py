"""Rhesis Haystack tracing bootstrap — import only from traced entrypoints.

Business modules (``pipeline``, ``session``, ``agents/*``, …) must never import
this module. Tracing is opt-in at the script or server boundary.
"""

from __future__ import annotations

import logging
import os

# Must precede any haystack import so span input/output content is captured.
os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")

logger = logging.getLogger(__name__)

_bootstrapped = False


def is_rhesis_tracing_configured() -> bool:
    """Return True when both Rhesis credentials needed for tracing are set.

    Matches the gate in ``app.py``: ``RhesisClient`` and ``RhesisConnector`` both
    need ``RHESIS_API_KEY`` and ``RHESIS_PROJECT_ID`` to ship spans reliably.
    """
    return bool(os.getenv("RHESIS_API_KEY") and os.getenv("RHESIS_PROJECT_ID"))


def enable_rhesis_tracing(name: str = "Visit-Prep") -> bool:
    """Bootstrap the global Haystack Rhesis tracer (idempotent).

    ``RhesisConnector.__init__`` resolves env config, get-or-creates the process-wide
    ``TracerProvider``, builds the high-fidelity ``RhesisTracer``, and calls
    ``haystack.tracing.enable_tracing`` globally. Its ``run()`` only sets per-run
    session context — we replace that with :func:`set_trace_session`. The connector
    is constructed once and never added to any pipeline.
    """
    global _bootstrapped
    if _bootstrapped:
        return True
    if not is_rhesis_tracing_configured():
        logger.info(
            "RHESIS_API_KEY/RHESIS_PROJECT_ID not set; Rhesis Haystack tracing disabled."
        )
        return False

    from haystack_integrations.components.connectors.rhesis import RhesisConnector

    # Construct once for side effects; discard — never add to a pipeline.
    RhesisConnector(name)
    _bootstrapped = True
    return True


def set_trace_session(session_id: str) -> None:
    """Group subsequent spans under one conversation in the Rhesis UI."""
    if not _bootstrapped:
        return
    from haystack_integrations.tracing.rhesis.tracer import tracing_context_var

    tracing_context_var.set({"session_id": session_id})


def flush_rhesis_tracing() -> None:
    """Best-effort flush of pending Haystack/Rhesis spans."""
    try:
        from haystack.tracing import tracer as haystack_tracer

        actual = getattr(haystack_tracer, "actual_tracer", None)
        if actual is not None and hasattr(actual, "flush"):
            actual.flush()
    except Exception:  # pragma: no cover - best-effort shutdown flush
        logger.debug("No Haystack tracer to flush", exc_info=True)

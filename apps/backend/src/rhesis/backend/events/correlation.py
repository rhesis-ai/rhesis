"""W3C trace context: propagation across the Celery boundary, and the
correlation ids every ``PlatformEvent`` carries.

Ids are never minted by a plain random UUID at a call site. They come off a
real ``SpanContext`` -- either the active span, one extracted from a message,
or, failing both, one built directly with :func:`_mint_span_context` -- and
move across process boundaries with OTel's own propagation API
(``opentelemetry.propagate``), already a dependency via
``opentelemetry-api``/``opentelemetry-sdk``. Sampling then rides the trace
flags in ``traceparent`` for free -- a bare UUID would have needed a hand
rolled, easy to get wrong sampling story of its own.

Why the fallback cannot go through ``trace.get_tracer(...).start_span()``,
which is what the obvious implementation (and the original design note this
module implements) reaches for: ``initialize_telemetry()``
(``telemetry/instrumentation.py``) deliberately returns without installing a
``TracerProvider`` at all when telemetry is globally off -- true for every
self-hosted deployment by default, and true for the Celery worker process,
which never calls ``initialize_telemetry()`` in the first place (that call
lives only in ``app/main.py``, the FastAPI process). With no provider
registered, OTel's global default answers every ``start_span()`` with a
no-op span whose context is invalid -- confirmed empirically, not assumed.
Reaching for a tracer here would silently reproduce the exact all-zero-id
failure this module exists to prevent, in precisely the deployment mode
where it matters most.

So the fallback constructs a ``SpanContext`` directly, the same primitive
OTel itself builds when *extracting* a remote context from a header that
was never locally recorded. It is real, valid, and propagates correctly; it
is simply not attached to this process's (possibly nonexistent) tracer
provider, so it will never appear in a locally exported span. That is
consistent with a caller having no telemetry to export in the first place.
"""

import logging
import secrets
from typing import Dict, Optional, Tuple

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

logger = logging.getLogger(__name__)


def _mint_span_context() -> SpanContext:
    """A fresh, valid, unattached-to-any-provider span context.

    Not a plain ``uuid4()``: the id widths (128-bit trace id, 64-bit span id)
    and the ``sampled`` trace flag must match the W3C shape so a genuine OTel
    collector downstream (``future-otel.md``) does not choke on it later.
    """
    return SpanContext(
        trace_id=secrets.randbits(128),
        span_id=secrets.randbits(64),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )


def _current_or_extracted(headers: Optional[Dict[str, str]]):
    """The span context this call should use: from ``headers`` if given and
    valid, else whatever is currently attached. Returns ``None`` if neither
    yields anything valid -- the caller decides what to do about that.
    """
    if headers:
        # An explicit empty Context() -- not the ambient one -- because some
        # propagators default to layering onto the current context when none
        # is given, which would silently pick up whatever happens to be
        # active on the calling thread instead of what was actually
        # propagated in these headers.
        extracted = extract(headers, context=otel_context.Context())
        span_context = trace.get_current_span(extracted).get_span_context()
        if span_context.is_valid:
            return span_context

    span_context = trace.get_current_span().get_span_context()
    return span_context if span_context.is_valid else None


def attach_from_headers(headers: Optional[Dict[str, str]]):
    """Extract a trace context from message headers and make it current.

    Returns an opaque token for :func:`detach`, or ``None`` if there was
    nothing valid to attach -- e.g. a task with no ``traceparent`` header,
    such as one dispatched outside ``launch_job``. Callers must not call
    :func:`detach` for a task that got ``None`` here; see ``celery/signals.py``
    for the paired dict-of-tokens pattern already used for usage attribution,
    which this mirrors.
    """
    if not headers:
        return None
    extracted = extract(headers, context=otel_context.Context())
    if not trace.get_current_span(extracted).get_span_context().is_valid:
        return None
    return otel_context.attach(extracted)


def detach(token) -> None:
    """Undo :func:`attach_from_headers`. Safe to call with ``None``."""
    if token is None:
        return
    try:
        otel_context.detach(token)
    except Exception:
        logger.warning("Failed to detach trace context", exc_info=True)


def resolve_ids(headers: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """Return ``(trace_id, span_id)`` as lowercase hex, never all-zero.

    Read-only -- does not attach or mutate anything. Two calling shapes:

    - With ``headers``: reads what those headers carry, e.g. building
      ``JobCancelled`` for a task revoked before ``task_prerun`` ever ran, so
      there is no ambient context to read instead.
    - Without ``headers``: reads whatever is currently attached. The normal
      case inside a job body, after ``task_prerun`` has already called
      :func:`attach_from_headers`.

    Falls back to :func:`_mint_span_context` when neither yields a valid
    context, so a caller with no trace context at all -- a script, or a
    request with nothing upstream of it -- still gets a non-zero id pair
    rather than propagating zeros forward. This id is not tied to any
    recorded span in this process; see the module docstring for why it
    cannot be.
    """
    span_context = _current_or_extracted(headers) or _mint_span_context()
    return format(span_context.trace_id, "032x"), format(span_context.span_id, "016x")


def prepare_dispatch(headers: Dict[str, str]) -> Tuple[str, str]:
    """Resolve ids for a job about to be dispatched, and write the matching
    ``traceparent`` into ``headers`` -- both from the exact same context.

    Not simply ``resolve_ids()`` followed by a separate ``inject()`` call:
    if there is no active span, ``resolve_ids()``'s fallback mints one that
    exists only for the instant this function runs. A later, separate
    ``inject()`` call would no longer see it as current and would write
    something else -- or nothing -- leaving the returned ids and the
    propagated header inconsistent with each other.
    """
    span_context = _current_or_extracted(None)
    if span_context is not None:
        inject(headers)
        return format(span_context.trace_id, "032x"), format(span_context.span_id, "016x")

    span_context = _mint_span_context()
    token = otel_context.attach(trace.set_span_in_context(NonRecordingSpan(span_context)))
    try:
        inject(headers)
    finally:
        otel_context.detach(token)
    return format(span_context.trace_id, "032x"), format(span_context.span_id, "016x")

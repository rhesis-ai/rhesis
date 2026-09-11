"""Event-loop-safe invocation for the endpoint HTTP routes.

:meth:`EndpointService.invoke_endpoint` interleaves psycopg2 calls -- the
endpoint lookup, the conversation trace lookup, the span write -- with the
awaits it makes on the target endpoint. A coroutine route handler that passed
it a live ``Session`` would run every one of those queries on the event loop,
blocking every other request in the worker for their duration.

So this module does what the batch runner already does: pre-fetch what the
invocation needs, run ``invoke_endpoint`` in its DB-free mode (``db=None``,
``deferred_trace=True``, endpoint passed in), then write the collected trace
afterwards. Each database segment runs in ``anyio.to_thread.run_sync``, one at
a time -- a Session is not thread-safe, and nothing here holds it across
concurrent tasks.
"""

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, Optional

import anyio
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.endpoint.files import enrich_files_with_extraction
from rhesis.backend.app.services.invokers.common.errors import EndpointInvocationError
from rhesis.backend.app.services.invokers.conversation import (
    ConversationTracker,
    find_conversation_id,
    get_conversation_store,
)
from rhesis.backend.app.services.invokers.tracing import persist_deferred_trace

if TYPE_CHECKING:
    from rhesis.backend.app.services.endpoint.service import EndpointService

logger = logging.getLogger(__name__)


def _conversation_id_for_trace(endpoint: Endpoint, input_data: Dict[str, Any]) -> Optional[str]:
    """The conversation ``invoke_endpoint`` will trace this call under.

    Mirrors the service: a stateless endpoint traces under the stored
    conversation it resumes, and otherwise starts a fresh one that by
    definition has no earlier trace; everything else traces under whichever
    conversation field the input carries.
    """
    if ConversationTracker.detect_stateless_mode(endpoint) and "messages" not in input_data:
        incoming = input_data.get("conversation_id")
        if incoming and get_conversation_store().exists(incoming):
            return str(incoming)
        return None
    return find_conversation_id(input_data)


def _existing_trace_id(
    db: Session,
    endpoint: Endpoint,
    input_data: Dict[str, Any],
    organization_id: str | None,
) -> Optional[str]:
    """The trace to continue for this conversation, or None to start one.

    ``invoke_endpoint`` looks this up itself when it has a session. We pass the
    answer in as ``trace_id=`` instead, which both the trace context manager and
    the SDK invoker prefer over their own lookup.
    """
    from rhesis.backend.app.crud.telemetry import get_trace_id_for_conversation
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        get_trace_id_from_pending_links,
    )

    if not endpoint.project_id:
        return None
    conversation_id = _conversation_id_for_trace(endpoint, input_data)
    if not conversation_id:
        return None

    trace_id = get_trace_id_for_conversation(
        db=db,
        conversation_id=conversation_id,
        project_id=str(endpoint.project_id),
        organization_id=organization_id,
    )
    # Turn 1's spans may not be ingested yet; the id is then still in the cache.
    return trace_id or get_trace_id_from_pending_links(conversation_id)


def _enriched_files(db: Session, input_data: Dict[str, Any], user_id: str | None) -> Optional[list]:
    """Extract text from inline files now, so the invocation doesn't have to.

    ``enrich_files_with_extraction`` resolves the caller's generation model (a
    query) before it can use the vision fallback. Doing it here keeps that
    query off the loop, and ``invoke_endpoint`` then takes its fast path
    because every file already carries ``extracted_text``. Returns None when
    there is nothing to do.
    """
    files = input_data.get("files")
    if not files:
        return None
    if not any(isinstance(f, dict) and "extracted_text" not in f for f in files):
        return None
    return enrich_files_with_extraction(files, db=db, user_id=user_id)


def _prefetch(
    service: "EndpointService",
    db: Session,
    endpoint_id: str,
    input_data: Dict[str, Any],
    organization_id: str | None,
    user_id: str | None,
    project_id: str | None,
) -> tuple[Endpoint, Optional[str], Optional[list]]:
    """Every query the invocation needs up front, in one thread hop.

    Runs in a worker thread. The caller awaits it, so nothing else touches the
    session while this is in flight.
    """
    endpoint = service._get_endpoint(db, endpoint_id, organization_id, project_id)
    trace_id = _existing_trace_id(db, endpoint, input_data, organization_id)
    files = _enriched_files(db, input_data, user_id)
    return endpoint, trace_id, files


def _pop_deferred_trace(result: Any) -> Any:
    """Take the in-memory trace off the result before it becomes the response.

    A successful invocation carries it under ``_deferred_trace``; an
    ``ErrorResponse`` carries it as the extra field ``deferred_trace``.
    """
    if isinstance(result, dict):
        return result.pop("_deferred_trace", None)
    extra = getattr(result, "__pydantic_extra__", None)
    if isinstance(extra, dict):
        return extra.pop("deferred_trace", None)
    return None


def _as_invocation_error(exc: Exception) -> EndpointInvocationError:
    """Report a database failure the way ``invoke_endpoint`` reports its own.

    The route's handler discriminates on ``error_type``, so a failed prefetch or
    trace write has to arrive as ours (``internal_error``), not as a bare 500
    from somewhere below the router.
    """
    return EndpointInvocationError(
        str(exc), transient=False, status_code=500, error_type="internal_error"
    )


async def invoke_endpoint_off_loop(
    service: "EndpointService",
    db: Session,
    endpoint_id: str,
    input_data: Dict[str, Any],
    organization_id: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
) -> Any:
    """Invoke an endpoint from the event loop without querying on it.

    Same result as ``invoke_endpoint``: the endpoint's mapped response (or an
    ``ErrorResponse``), with ``trace_id`` stamped on it and the invocation span
    written under the caller's transaction.
    """
    try:
        endpoint, trace_id, files = await anyio.to_thread.run_sync(
            partial(
                _prefetch,
                service,
                db,
                endpoint_id,
                input_data,
                organization_id,
                user_id,
                project_id,
            )
        )
    except (HTTPException, EndpointInvocationError):
        raise
    except Exception as exc:
        raise _as_invocation_error(exc) from exc

    if files is not None:
        input_data = {**input_data, "files": files}

    result = await service.invoke_endpoint(
        None,
        endpoint_id,
        input_data,
        organization_id=organization_id,
        user_id=user_id,
        endpoint=endpoint,
        deferred_trace=True,
        trace_id=trace_id,
        project_id=project_id,
    )

    deferred = _pop_deferred_trace(result)
    if deferred is not None:
        try:
            await anyio.to_thread.run_sync(partial(persist_deferred_trace, db, deferred))
        except Exception as exc:
            raise _as_invocation_error(exc) from exc

    return result

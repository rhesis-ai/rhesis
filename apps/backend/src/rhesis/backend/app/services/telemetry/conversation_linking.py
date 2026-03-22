"""Deferred linking for conversation traces.

Three separate concerns are handled here, each with its own cache:

1. **Conversation ID linking** (first-turn only)
   Stateful endpoints generate a session/conversation ID in their
   response.  The first turn's trace is stored with
   ``conversation_id=NULL`` because the ID wasn't known yet.  After
   invocation, the backend discovers the ID and tries an immediate
   UPDATE.  If the SDK spans haven't arrived yet (async export), the
   mapping is parked and applied when the spans are ingested.

2. **Mapped output injection** (every SDK turn)
   The SDK tracer sets ``rhesis.conversation.input`` per-span, but
   cannot set ``rhesis.conversation.output`` because it only has the
   raw function return value — not the response-mapped output.  The
   backend parks the mapped output after invocation and injects it
   into the span's attributes *before* storage, when the SDK spans
   arrive at the telemetry ingest endpoint.

3. **Input file linking** (SDK turns with file attachments)
   When a test includes file attachments, the files are available at
   invocation time but the SDK trace record hasn't been created yet.
   The backend parks the file metadata after invocation and creates
   ``File`` records linked to the stored ``Trace`` when the SDK spans
   arrive at the telemetry ingest endpoint — after storage.

Caches are stored in Redis (shared across workers/replicas) with an
automatic in-memory fallback when Redis is unavailable (e.g. local
development without Redis).

**Why the SDK path needs deferred injection (vs. REST):**
REST/WebSocket endpoints (see ``tracing.py``) create their trace span
synchronously inside ``create_invocation_trace()``, so both input and
output are available when the span is constructed — no caching needed.
SDK endpoints, however, emit spans asynchronously via the SDK's
``BatchSpanProcessor``.  The backend receives the mapped output after
``invoke()`` returns, but the SDK spans haven't arrived at the
``/telemetry/traces`` ingest endpoint yet.  This module bridges that
gap by parking the output/files and injecting them when the spans arrive.
"""

import json
import logging
import time
from typing import Any, Dict, List, NamedTuple, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # seconds

# Import lazily inside functions to avoid circular imports, but
# keep a module-level alias for the max I/O length so the cache
# class (which runs outside those functions) can reference it.
_MAX_IO_LENGTH = 10000  # synced with ConversationConstants.MAX_IO_LENGTH


# ---------------------------------------------------------------
# Data classes (kept for backward compatibility with tests)
# ---------------------------------------------------------------


class PendingConversationLink(NamedTuple):
    """A deferred conversation-id-to-trace mapping awaiting span arrival."""

    conversation_id: str
    organization_id: str
    registered_at: float


class PendingOutput(NamedTuple):
    """Mapped output waiting to be injected into an arriving SDK span."""

    mapped_output: str
    registered_at: float


class PendingFiles(NamedTuple):
    """Input files waiting to be linked to a Trace when SDK spans arrive."""

    files_json: str
    organization_id: str
    registered_at: float


# ---------------------------------------------------------------
# Redis key prefixes
# ---------------------------------------------------------------

_PREFIX_PENDING = "convlink:pending:"
_PREFIX_REVERSE = "convlink:reverse:"
_PREFIX_OUTPUT = "convlink:output:"
_PREFIX_FILES = "convlink:files:"


class ConversationLinkingCache(RedisBackedCache):
    """Redis-backed cache with in-memory fallback for conversation linking.

    Uses synchronous redis.Redis (not asyncio) because all callers are sync.
    Falls back to process-local dicts when Redis is unavailable.
    """

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.CONVERSATION_LINKING,
            cache_name="conversation-linking",
            ttl=_CACHE_TTL,
        )
        # Backward-compatible in-memory dicts (used by tests and in-memory fallback)
        self._pending_links: Dict[str, PendingConversationLink] = {}
        self._pending_outputs: Dict[str, PendingOutput] = {}
        self._pending_files: Dict[str, PendingFiles] = {}

    # -----------------------------------------------------------
    # Conversation link methods
    # -----------------------------------------------------------

    def register_link(
        self,
        trace_id: str,
        conversation_id: str,
        organization_id: str,
    ) -> None:
        """Park a conversation-id link for deferred application."""
        if self._using_redis:
            try:
                payload = json.dumps(
                    {
                        "conversation_id": conversation_id,
                        "organization_id": organization_id,
                    }
                )
                pipe = self._redis.pipeline()
                pipe.set(
                    f"{_PREFIX_PENDING}{trace_id}",
                    payload,
                    ex=_CACHE_TTL,
                )
                pipe.set(
                    f"{_PREFIX_REVERSE}{conversation_id}",
                    trace_id,
                    ex=_CACHE_TTL,
                )
                pipe.execute()
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_link, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_links[trace_id] = PendingConversationLink(
                conversation_id=conversation_id,
                organization_id=organization_id,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_links)

    def get_trace_id_for_conversation(self, conversation_id: str) -> Optional[str]:
        """Reverse-lookup: find the trace_id parked for a conversation."""
        if self._using_redis:
            try:
                result = self._redis.get(f"{_PREFIX_REVERSE}{conversation_id}")
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning(
                    "Redis read failed for get_trace_id_for_conversation, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            for tid, link in self._pending_links.items():
                if link.conversation_id == conversation_id:
                    return tid
        return None

    def pop_links_for_traces(self, trace_ids: List[str]) -> List[tuple]:
        """Pop and return pending links matching any of the given trace_ids.

        Returns list of (trace_id, conversation_id, organization_id) tuples.
        """
        if self._using_redis:
            try:
                return self._pop_links_redis(trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_links_for_traces, "
                    f"falling back to memory: {exc}"
                )

        matched = []
        with self._lock:
            for tid in trace_ids:
                link = self._pending_links.pop(tid, None)
                if link is not None:
                    matched.append((tid, link.conversation_id, link.organization_id))
        return matched

    def _pop_links_redis(self, trace_ids: List[str]) -> List[tuple]:
        """Atomically fetch and delete pending link keys from Redis."""
        keys = [f"{_PREFIX_PENDING}{tid}" for tid in trace_ids]
        values = self._redis.mget(keys)

        matched = []
        delete_keys: List[str] = []
        for tid, val in zip(trace_ids, values):
            if val is None:
                continue
            data = json.loads(val)
            matched.append((tid, data["conversation_id"], data["organization_id"]))
            delete_keys.append(f"{_PREFIX_PENDING}{tid}")
            delete_keys.append(f"{_PREFIX_REVERSE}{data['conversation_id']}")

        if delete_keys:
            self._redis.delete(*delete_keys)

        return matched

    # -----------------------------------------------------------
    # Output methods
    # -----------------------------------------------------------

    def register_output(self, trace_id: str, mapped_output: str) -> None:
        """Park a mapped output for injection when SDK spans arrive."""
        if self._using_redis:
            try:
                self._redis.set(
                    f"{_PREFIX_OUTPUT}{trace_id}",
                    mapped_output[:_MAX_IO_LENGTH],
                    ex=_CACHE_TTL,
                )
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_output, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_outputs[trace_id] = PendingOutput(
                mapped_output=mapped_output,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_outputs)

    def pop_outputs_for_traces(self, trace_ids: List[str]) -> Dict[str, str]:
        """Pop and return pending outputs matching any of the given trace_ids.

        Returns dict of {trace_id: mapped_output}.
        """
        if self._using_redis:
            try:
                return self._pop_outputs_redis(trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_outputs_for_traces, "
                    f"falling back to memory: {exc}"
                )

        matched = {}
        with self._lock:
            for tid in trace_ids:
                entry = self._pending_outputs.pop(tid, None)
                if entry is not None:
                    matched[tid] = entry.mapped_output
        return matched

    def _pop_outputs_redis(self, trace_ids: List[str]) -> Dict[str, str]:
        """Atomically fetch and delete pending output keys from Redis."""
        keys = [f"{_PREFIX_OUTPUT}{tid}" for tid in trace_ids]
        values = self._redis.mget(keys)

        matched = {}
        delete_keys = []
        for tid, val in zip(trace_ids, values):
            if val is not None:
                matched[tid] = val
                delete_keys.append(f"{_PREFIX_OUTPUT}{tid}")

        if delete_keys:
            self._redis.delete(*delete_keys)

        return matched

    # -----------------------------------------------------------
    # File methods
    # -----------------------------------------------------------

    def register_files(
        self,
        trace_id: str,
        files_json: str,
        organization_id: str,
    ) -> None:
        """Park input files for deferred creation when SDK spans arrive."""
        if self._using_redis:
            try:
                payload = json.dumps(
                    {
                        "files": files_json,
                        "organization_id": organization_id,
                    }
                )
                self._redis.set(
                    f"{_PREFIX_FILES}{trace_id}",
                    payload,
                    ex=_CACHE_TTL,
                )
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_files, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_files[trace_id] = PendingFiles(
                files_json=files_json,
                organization_id=organization_id,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_files)

    def pop_files_for_traces(self, trace_ids: List[str]) -> Dict[str, tuple]:
        """Pop and return pending files matching any of the given trace_ids.

        Returns dict of {trace_id: (files_json, organization_id)}.
        """
        if self._using_redis:
            try:
                return self._pop_files_redis(trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_files_for_traces, "
                    f"falling back to memory: {exc}"
                )

        matched = {}
        with self._lock:
            for tid in trace_ids:
                entry = self._pending_files.pop(tid, None)
                if entry is not None:
                    matched[tid] = (
                        entry.files_json,
                        entry.organization_id,
                    )
        return matched

    def _pop_files_redis(self, trace_ids: List[str]) -> Dict[str, tuple]:
        """Atomically fetch and delete pending file keys from Redis."""
        keys = [f"{_PREFIX_FILES}{tid}" for tid in trace_ids]
        values = self._redis.mget(keys)

        matched = {}
        delete_keys = []
        for tid, val in zip(trace_ids, values):
            if val is not None:
                data = json.loads(val)
                matched[tid] = (
                    data["files"],
                    data["organization_id"],
                )
                delete_keys.append(f"{_PREFIX_FILES}{tid}")

        if delete_keys:
            self._redis.delete(*delete_keys)

        return matched


# ---------------------------------------------------------------
# Module-level singleton and public API
# ---------------------------------------------------------------

_cache = ConversationLinkingCache()


def initialize_cache() -> None:
    """Initialize the conversation linking cache (call at app startup)."""
    _cache.initialize()


# ---------------------------------------------------------------
# 1. Conversation ID linking (first-turn patching)
# ---------------------------------------------------------------


def register_pending_conversation_link(
    trace_id: str,
    conversation_id: str,
    organization_id: str,
) -> None:
    """Park a conversation-id link for deferred application.

    Called when ``crud.update_conversation_id_for_trace()`` returns 0
    because the SDK's spans have not been ingested yet.
    """
    _cache.register_link(trace_id, conversation_id, organization_id)
    logger.debug(
        f"[CONVERSATION_LINKING] Parked pending link: "
        f"trace_id={trace_id}, conversation_id={conversation_id}"
    )


def get_trace_id_from_pending_links(
    conversation_id: str,
) -> Optional[str]:
    """Look up a trace_id from the pending conversation links cache.

    When Turn 1's spans haven't been ingested yet, the DB query in
    ``get_trace_id_for_conversation()`` returns None.  But the
    trace_id -> conversation_id mapping was already parked by
    ``_link_first_turn_trace()`` in the same request.  This function
    does a reverse lookup so Turn 2 can find and reuse Turn 1's
    trace_id without waiting for span ingestion.

    Returns the trace_id if found, None otherwise.
    """
    return _cache.get_trace_id_for_conversation(conversation_id)


def apply_pending_conversation_links(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Apply parked conversation-id links for recently stored spans.

    Called by the telemetry ingest endpoint after spans are committed.
    Returns the total number of span rows updated.

    RLS note: We switch the DB session's tenant context per-link so
    the UPDATE is visible through the RLS policy on the ``trace``
    table.
    """
    if not stored_spans:
        return 0

    unique_trace_ids = list({span.trace_id for span in stored_spans})
    matched = _cache.pop_links_for_traces(unique_trace_ids)

    if not matched:
        return 0

    from rhesis.backend.app.database import set_session_variables

    total = 0
    for trace_id, conversation_id, organization_id in matched:
        set_session_variables(db, organization_id, "")

        count = crud.update_conversation_id_for_trace(
            db, trace_id, conversation_id, organization_id
        )
        total += count
        logger.info(
            f"[CONVERSATION_LINKING] Applied pending link: "
            f"trace_id={trace_id}, "
            f"conversation_id={conversation_id}, "
            f"updated={count} spans"
        )

    return total


# ---------------------------------------------------------------
# 2. Mapped output injection (per-turn, before span storage)
# ---------------------------------------------------------------


def register_pending_output(
    trace_id: str,
    mapped_output: str,
) -> None:
    """Park a mapped output for injection when SDK spans arrive.

    Called by ``SdkEndpointInvoker.invoke()`` after response mapping.
    The SDK tracer already stamps ``rhesis.conversation.input`` on
    each root span — only the output needs to be added by the
    backend.
    """
    _cache.register_output(trace_id, mapped_output)
    logger.debug(f"[CONVERSATION_IO] Parked pending output for trace_id={trace_id}")


def inject_pending_output(
    spans: List[Any],
) -> int:
    """Inject parked mapped output into span attributes before storage.

    Called by the telemetry ingest endpoint *before*
    ``create_trace_spans()`` so the output is part of the span from
    the moment it is stored — no post-hoc UPDATE required.

    Only injects into root spans (no parent) that already carry
    ``rhesis.conversation.input`` but lack ``rhesis.conversation.output``.

    Args:
        spans: Mutable list of OTELSpan / OTELSpanCreate objects
               whose ``attributes`` dict will be mutated in place.

    Returns:
        Number of spans that received an output injection.
    """
    from rhesis.sdk.telemetry.constants import (
        ConversationContext as ConversationConstants,
    )

    input_key = ConversationConstants.SpanAttributes.CONVERSATION_INPUT
    output_key = ConversationConstants.SpanAttributes.CONVERSATION_OUTPUT

    # Collect unique trace_ids from the batch
    trace_ids = list({span.trace_id for span in spans})

    matched = _cache.pop_outputs_for_traces(trace_ids)

    if not matched:
        return 0

    injected_count = 0
    for span in spans:
        pending_output = matched.get(span.trace_id)
        if pending_output is None:
            continue

        # Only inject into root spans that have input but no output
        is_root = not span.parent_span_id
        has_input = input_key in span.attributes
        has_output = output_key in span.attributes

        if is_root and has_input and not has_output:
            span.attributes[output_key] = pending_output[:_MAX_IO_LENGTH]
            injected_count += 1
            logger.debug(
                f"[CONVERSATION_IO] Injected output into span "
                f"{span.span_id} (trace {span.trace_id})"
            )

    return injected_count


# ---------------------------------------------------------------
# 3. Input file linking (post-storage, when SDK spans arrive)
# ---------------------------------------------------------------


def register_pending_files(
    trace_id: str,
    files: List[Dict[str, Any]],
    organization_id: str,
) -> None:
    """Park input files for deferred creation when SDK spans arrive.

    Called by ``SdkEndpointInvoker.invoke()`` when ``input_data``
    contains files.  The file metadata (including base64 content) is
    serialized to JSON and stored in the cache.  When the SDK spans
    arrive at ``/telemetry/traces``, ``apply_pending_files()`` pops
    the cached data and creates ``File`` records linked to the stored
    ``Trace`` record.
    """
    files_json = json.dumps(files)
    _cache.register_files(trace_id, files_json, organization_id)
    logger.debug(f"[FILE_LINKING] Parked {len(files)} pending file(s) for trace_id={trace_id}")


def apply_pending_files(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Create File records for parked input files after span storage.

    Called by the telemetry ingest endpoint after spans are committed.
    For each stored span whose ``trace_id`` has parked files, creates
    ``File`` records with ``entity_type='Trace'`` and
    ``entity_id=span.id`` (the DB primary key).

    Returns the total number of files created.
    """
    if not stored_spans:
        return 0

    unique_trace_ids = list({span.trace_id for span in stored_spans})
    matched = _cache.pop_files_for_traces(unique_trace_ids)

    if not matched:
        return 0

    import base64

    from rhesis.backend.app import schemas
    from rhesis.backend.app.database import set_session_variables

    total = 0
    for span in stored_spans:
        entry = matched.get(span.trace_id)
        if entry is None:
            continue

        # Only create files on the root span (no parent)
        if span.parent_span_id:
            continue

        files_json, organization_id = entry
        files = json.loads(files_json)

        set_session_variables(db, organization_id, "")

        for idx, file_data in enumerate(files):
            if not isinstance(file_data, dict):
                continue

            content_b64 = file_data.get("data")
            if not content_b64:
                continue

            try:
                content = base64.b64decode(content_b64)
            except Exception:
                logger.warning(f"Failed to decode base64 for pending file {idx}")
                continue

            file_create = schemas.FileCreate(
                filename=file_data.get("filename", f"file_{idx}"),
                content_type=file_data.get("content_type", "application/octet-stream"),
                size_bytes=len(content),
                content=content,
                entity_id=span.id,
                entity_type="Trace",
                position=idx,
            )
            crud.create_file(db, file_create, organization_id=organization_id)
            total += 1

        logger.info(
            f"[FILE_LINKING] Created {len(files)} file(s) for "
            f"trace_id={span.trace_id}, span_id={span.id}"
        )

    return total


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def _evict_stale(cache: dict) -> None:
    """Remove entries older than ``_CACHE_TTL`` (caller holds lock)."""
    cutoff = time.monotonic() - _CACHE_TTL
    stale_keys = [key for key, entry in cache.items() if entry.registered_at < cutoff]
    for key in stale_keys:
        del cache[key]

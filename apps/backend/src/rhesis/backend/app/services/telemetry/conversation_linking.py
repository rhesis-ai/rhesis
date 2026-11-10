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
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.telemetry import update_conversation_id_for_trace
from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # seconds

# Import lazily inside functions to avoid circular imports, but
# keep a module-level alias for the max I/O length so the cache
# class (which runs outside those functions) can reference it.
_MAX_IO_LENGTH = 10000  # synced with ConversationConstants.MAX_IO_LENGTH


# ---------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------


class PendingConversationLink(NamedTuple):
    """A deferred conversation-id-to-trace mapping awaiting span arrival."""

    conversation_id: str
    registered_at: float


class PendingOutput(NamedTuple):
    """Mapped output waiting to be injected into an arriving SDK span."""

    mapped_output: str
    registered_at: float


class PendingFiles(NamedTuple):
    """Input files waiting to be linked to a Trace when SDK spans arrive."""

    files_json: str
    registered_at: float


# In-memory entries are keyed by (organization_id, project_id, trace_id).
ScopedKey = Tuple[str, str, str]


# ---------------------------------------------------------------
# Redis key prefixes
# ---------------------------------------------------------------

# Every key carries the owning org and project, so tenants that reuse a
# conversation or trace id never see each other's entries. The "v2" segment
# keeps these apart from the un-scoped keys written by older releases.
_PREFIX_PENDING = "convlink:v2:pending:"
_PREFIX_REVERSE = "convlink:v2:reverse:"
_PREFIX_OUTPUT = "convlink:v2:output:"
_PREFIX_FILES = "convlink:v2:files:"


def _key(prefix: str, organization_id: str, project_id: str, item_id: str) -> str:
    return f"{prefix}{organization_id}:{project_id}:{item_id}"


def _scope(organization_id: Any, project_id: Any) -> Optional[Tuple[str, str]]:
    """Stringify a tenant scope, or None when either part is missing.

    Callers pass raw ids (UUID, str or None), so a missing id never becomes
    the literal string "None" and a shared fake scope.
    """
    if not organization_id or not project_id:
        return None
    return str(organization_id), str(project_id)


class ConversationLinkingCache(RedisBackedCache):
    """Redis-backed cache with in-memory fallback for conversation linking.

    Uses synchronous redis.Redis (not asyncio) because all callers are sync.
    Falls back to process-local dicts when Redis is unavailable. Every entry
    is scoped to an (organization_id, project_id) pair; lookups only see
    entries in the caller's scope.
    """

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.CONVERSATION_LINKING,
            cache_name="conversation-linking",
            ttl=_CACHE_TTL,
        )
        self._pending_links: Dict[ScopedKey, PendingConversationLink] = {}
        self._pending_outputs: Dict[ScopedKey, PendingOutput] = {}
        self._pending_files: Dict[ScopedKey, PendingFiles] = {}

    def _on_reconnect(self) -> None:
        # Pops read Redis now, so entries parked here would never be found.
        with self._lock:
            for pending in (self._pending_links, self._pending_outputs, self._pending_files):
                _evict_stale(pending)
            links, self._pending_links = self._pending_links, {}
            outputs, self._pending_outputs = self._pending_outputs, {}
            files, self._pending_files = self._pending_files, {}
        for (org, project, trace_id), link in links.items():
            self.register_link(org, project, trace_id, link.conversation_id)
        for (org, project, trace_id), output in outputs.items():
            self.register_output(org, project, trace_id, output.mapped_output)
        for (org, project, trace_id), entry in files.items():
            self.register_files(org, project, trace_id, entry.files_json)

    # -----------------------------------------------------------
    # Conversation link methods
    # -----------------------------------------------------------

    def register_link(
        self,
        organization_id: str,
        project_id: str,
        trace_id: str,
        conversation_id: str,
    ) -> None:
        """Park a conversation-id link for deferred application."""
        if self._using_redis:
            try:
                pipe = self._redis.pipeline()
                pipe.set(
                    _key(_PREFIX_PENDING, organization_id, project_id, trace_id),
                    json.dumps({"conversation_id": conversation_id}),
                    ex=_CACHE_TTL,
                )
                pipe.set(
                    _key(_PREFIX_REVERSE, organization_id, project_id, conversation_id),
                    trace_id,
                    ex=_CACHE_TTL,
                )
                pipe.execute()
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_link, falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_links[(organization_id, project_id, trace_id)] = PendingConversationLink(
                conversation_id=conversation_id,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_links)

    def get_trace_id_for_conversation(
        self,
        organization_id: str,
        project_id: str,
        conversation_id: str,
    ) -> Optional[str]:
        """Reverse-lookup: find the trace_id parked for a conversation in this scope."""
        if self._using_redis:
            try:
                result = self._redis.get(
                    _key(_PREFIX_REVERSE, organization_id, project_id, conversation_id)
                )
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning(
                    "Redis read failed for get_trace_id_for_conversation, "
                    f"falling back to memory: {exc}"
                )

        with self._lock:
            for (org, project, tid), link in self._pending_links.items():
                if (
                    org == organization_id
                    and project == project_id
                    and link.conversation_id == conversation_id
                ):
                    return tid
        return None

    def pop_links_for_traces(
        self,
        organization_id: str,
        project_id: str,
        trace_ids: List[str],
    ) -> List[Tuple[str, str]]:
        """Pop pending links in this scope for any of the given trace_ids.

        Returns a list of (trace_id, conversation_id) tuples.
        """
        if self._using_redis:
            try:
                return self._pop_links_redis(organization_id, project_id, trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_links_for_traces, falling back to memory: {exc}"
                )

        matched = []
        with self._lock:
            for tid in trace_ids:
                link = self._pending_links.pop((organization_id, project_id, tid), None)
                if link is not None:
                    matched.append((tid, link.conversation_id))
        return matched

    def _pop_links_redis(
        self,
        organization_id: str,
        project_id: str,
        trace_ids: List[str],
    ) -> List[Tuple[str, str]]:
        """Fetch and delete pending link keys from Redis."""
        keys = [_key(_PREFIX_PENDING, organization_id, project_id, tid) for tid in trace_ids]
        values = self._redis.mget(keys)

        matched = []
        delete_keys: List[str] = []
        for tid, key, val in zip(trace_ids, keys, values, strict=True):
            if val is None:
                continue
            conversation_id = json.loads(val)["conversation_id"]
            matched.append((tid, conversation_id))
            delete_keys.append(key)
            delete_keys.append(_key(_PREFIX_REVERSE, organization_id, project_id, conversation_id))

        if delete_keys:
            self._redis.delete(*delete_keys)

        return matched

    # -----------------------------------------------------------
    # Output methods
    # -----------------------------------------------------------

    def register_output(
        self,
        organization_id: str,
        project_id: str,
        trace_id: str,
        mapped_output: str,
    ) -> None:
        """Park a mapped output for injection when SDK spans arrive."""
        if self._using_redis:
            try:
                self._redis.set(
                    _key(_PREFIX_OUTPUT, organization_id, project_id, trace_id),
                    mapped_output[:_MAX_IO_LENGTH],
                    ex=_CACHE_TTL,
                )
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_output, falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_outputs[(organization_id, project_id, trace_id)] = PendingOutput(
                mapped_output=mapped_output,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_outputs)

    def pop_outputs_for_traces(
        self,
        organization_id: str,
        project_id: str,
        trace_ids: List[str],
    ) -> Dict[str, str]:
        """Pop pending outputs in this scope for any of the given trace_ids.

        Returns dict of {trace_id: mapped_output}.
        """
        if self._using_redis:
            try:
                return self._pop_plain_redis(_PREFIX_OUTPUT, organization_id, project_id, trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_outputs_for_traces, falling back to memory: {exc}"
                )

        matched = {}
        with self._lock:
            for tid in trace_ids:
                entry = self._pending_outputs.pop((organization_id, project_id, tid), None)
                if entry is not None:
                    matched[tid] = entry.mapped_output
        return matched

    def _pop_plain_redis(
        self,
        prefix: str,
        organization_id: str,
        project_id: str,
        trace_ids: List[str],
    ) -> Dict[str, str]:
        """Fetch and delete string values stored per trace_id in this scope."""
        keys = [_key(prefix, organization_id, project_id, tid) for tid in trace_ids]
        values = self._redis.mget(keys)

        matched = {}
        delete_keys = []
        for tid, key, val in zip(trace_ids, keys, values, strict=True):
            if val is not None:
                matched[tid] = val
                delete_keys.append(key)

        if delete_keys:
            self._redis.delete(*delete_keys)

        return matched

    # -----------------------------------------------------------
    # File methods
    # -----------------------------------------------------------

    def register_files(
        self,
        organization_id: str,
        project_id: str,
        trace_id: str,
        files_json: str,
    ) -> None:
        """Park input files for deferred creation when SDK spans arrive."""
        if self._using_redis:
            try:
                self._redis.set(
                    _key(_PREFIX_FILES, organization_id, project_id, trace_id),
                    files_json,
                    ex=_CACHE_TTL,
                )
                return
            except Exception as exc:
                logger.warning(
                    f"Redis write failed for register_files, falling back to memory: {exc}"
                )

        with self._lock:
            self._pending_files[(organization_id, project_id, trace_id)] = PendingFiles(
                files_json=files_json,
                registered_at=time.monotonic(),
            )
            _evict_stale(self._pending_files)

    def pop_files_for_traces(
        self,
        organization_id: str,
        project_id: str,
        trace_ids: List[str],
    ) -> Dict[str, str]:
        """Pop pending files in this scope for any of the given trace_ids.

        Returns dict of {trace_id: files_json}.
        """
        if self._using_redis:
            try:
                return self._pop_plain_redis(_PREFIX_FILES, organization_id, project_id, trace_ids)
            except Exception as exc:
                logger.warning(
                    f"Redis read failed for pop_files_for_traces, falling back to memory: {exc}"
                )

        matched = {}
        with self._lock:
            for tid in trace_ids:
                entry = self._pending_files.pop((organization_id, project_id, tid), None)
                if entry is not None:
                    matched[tid] = entry.files_json
        return matched


# ---------------------------------------------------------------
# Module-level singleton and public API
# ---------------------------------------------------------------

_cache = ConversationLinkingCache()


def initialize_cache() -> None:
    """Initialize the conversation linking cache (call at app startup)."""
    _cache.initialize()


def _get_cache() -> ConversationLinkingCache:
    _cache._reconnect_if_due()
    return _cache


# ---------------------------------------------------------------
# 1. Conversation ID linking (first-turn patching)
# ---------------------------------------------------------------


def register_pending_conversation_link(
    trace_id: str,
    conversation_id: str,
    organization_id: Any,
    project_id: Any,
) -> None:
    """Park a conversation-id link for deferred application.

    Called when ``update_conversation_id_for_trace()`` returns 0
    because the SDK's spans have not been ingested yet.
    """
    scope = _scope(organization_id, project_id)
    if scope is None:
        return
    _get_cache().register_link(*scope, trace_id, conversation_id)
    logger.debug(
        f"[CONVERSATION_LINKING] Parked pending link: "
        f"trace_id={trace_id}, conversation_id={conversation_id}"
    )


def get_trace_id_from_pending_links(
    conversation_id: str,
    organization_id: Any,
    project_id: Any,
) -> Optional[str]:
    """Look up a trace_id from the pending conversation links cache.

    When Turn 1's spans haven't been ingested yet, the DB query in
    ``get_trace_id_for_conversation()`` returns None.  But the
    trace_id -> conversation_id mapping was already parked by
    ``_link_first_turn_trace()`` in the same request.  This function
    does a reverse lookup so Turn 2 can find and reuse Turn 1's
    trace_id without waiting for span ingestion.

    Only links parked under the caller's organization and project are
    visible. Returns the trace_id if found, None otherwise.
    """
    scope = _scope(organization_id, project_id)
    if scope is None:
        return None
    return _get_cache().get_trace_id_for_conversation(*scope, conversation_id)


def _trace_ids_by_scope(stored_spans: List[models.Trace]) -> Dict[Tuple[str, str], List[str]]:
    """Group trace_ids by the (organization_id, project_id) on the stored rows."""
    grouped: Dict[Tuple[str, str], set] = {}
    for span in stored_spans:
        if span.organization_id is None or span.project_id is None:
            continue
        scope = (str(span.organization_id), str(span.project_id))
        grouped.setdefault(scope, set()).add(span.trace_id)
    return {scope: list(trace_ids) for scope, trace_ids in grouped.items()}


def apply_pending_conversation_links(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Apply parked conversation-id links for recently stored spans.

    Called by the post-ingest job after spans are committed, with ``db``
    already bound to the ingesting tenant. The cache scope comes from the
    stored trace rows, never from the cache entry.
    Returns the total number of span rows updated.
    """
    if not stored_spans:
        return 0

    cache = _get_cache()
    total = 0
    for (organization_id, project_id), trace_ids in _trace_ids_by_scope(stored_spans).items():
        matched = cache.pop_links_for_traces(organization_id, project_id, trace_ids)
        for trace_id, conversation_id in matched:
            count = update_conversation_id_for_trace(db, trace_id, conversation_id, organization_id)
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
    organization_id: Any,
    project_id: Any,
) -> None:
    """Park a mapped output for injection when SDK spans arrive.

    Called by ``SdkEndpointInvoker.invoke()`` after response mapping.
    The SDK tracer already stamps ``rhesis.conversation.input`` on
    each root span — only the output needs to be added by the
    backend. ``organization_id``/``project_id`` must be the scope the
    spans will be ingested under.
    """
    scope = _scope(organization_id, project_id)
    if scope is None:
        return
    _get_cache().register_output(*scope, trace_id, mapped_output)
    logger.debug(f"[CONVERSATION_IO] Parked pending output for trace_id={trace_id}")


def inject_pending_output(
    spans: List[Any],
    organization_id: Any,
    project_id: Any,
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
        organization_id: The authenticated ingesting organization.
        project_id: The project the spans are being stored under.

    Returns:
        Number of spans that received an output injection.
    """
    from rhesis.telemetry.constants import (
        ConversationContext as ConversationConstants,
    )

    scope = _scope(organization_id, project_id)
    if not spans or scope is None:
        return 0

    input_key = ConversationConstants.SpanAttributes.CONVERSATION_INPUT
    output_key = ConversationConstants.SpanAttributes.CONVERSATION_OUTPUT

    trace_ids = list({span.trace_id for span in spans})

    matched = _get_cache().pop_outputs_for_traces(*scope, trace_ids)

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
    files,
    organization_id: Any,
    project_id: Any,
) -> None:
    """Park FileReference metadata for deferred entity linking when SDK spans arrive.

    ``files`` can be a List[FileReference] (test-execution path) or a
    List[Dict] (legacy inline-base64 dicts from the playground path).
    Only metadata is serialised to the cache — no base64 bytes.
    """
    scope = _scope(organization_id, project_id)
    if scope is None:
        return
    try:
        from rhesis.sdk.connector.types import FileReference

        serialisable = [f.model_dump() if isinstance(f, FileReference) else f for f in files]
    except ImportError:
        serialisable = files

    files_json = json.dumps(serialisable)
    _get_cache().register_files(*scope, trace_id, files_json)
    logger.debug(f"[FILE_LINKING] Parked {len(files)} pending file(s) for trace_id={trace_id}")


def apply_pending_files(
    db: Session,
    stored_spans: List[models.Trace],
) -> int:
    """Link already-uploaded File rows to the stored Trace span.

    For FileReference entries (test-execution path): the File row already
    exists — this function only updates entity_id/entity_type to point at the
    Trace span.  No base64 decoding, no storage writes.

    For legacy inline-base64 dicts (playground path): creates a File row with
    storage upload (backward compat until the playground migrates to upload-first).

    ``db`` is already bound to the ingesting tenant; the cache scope comes
    from the stored trace rows. Returns the total number of files linked or created.
    """
    if not stored_spans:
        return 0

    cache = _get_cache()
    matched: Dict[Tuple[str, str, str], str] = {}
    for (organization_id, project_id), trace_ids in _trace_ids_by_scope(stored_spans).items():
        for tid, files_json in cache.pop_files_for_traces(
            organization_id, project_id, trace_ids
        ).items():
            matched[(organization_id, project_id, tid)] = files_json

    if not matched:
        return 0

    from rhesis.backend.app import schemas

    total = 0
    for span in stored_spans:
        # Only process files on the root span (no parent)
        if span.parent_span_id or span.organization_id is None or span.project_id is None:
            continue

        organization_id = str(span.organization_id)
        files_json = matched.get((organization_id, str(span.project_id), span.trace_id))
        if files_json is None:
            continue

        files = json.loads(files_json)

        for idx, file_data in enumerate(files):
            if not isinstance(file_data, dict):
                continue

            # FileReference path (test-execution): file row already exists
            file_id = file_data.get("id")
            if file_id:
                try:
                    import uuid

                    from rhesis.backend.app.crud import file as file_crud

                    file_crud.link_file_to_entity(
                        db,
                        file_id=uuid.UUID(file_id),
                        entity_id=span.id,
                        entity_type="Trace",
                    )
                    total += 1
                    logger.debug(
                        f"[FILE_LINKING] Linked file_id={file_id} to "
                        f"trace_id={span.trace_id}, span_id={span.id}"
                    )
                except Exception as exc:
                    logger.warning(f"[FILE_LINKING] Failed to link file_id={file_id}: {exc}")
                continue

            # Legacy inline-base64 dict (playground path): create file row
            import base64 as _b64

            content_b64 = file_data.get("data")
            if not content_b64:
                continue

            try:
                content = _b64.b64decode(content_b64)
            except Exception:
                logger.warning(f"Failed to decode base64 for pending file {idx}")
                continue

            file_create = schemas.FileCreate(
                filename=file_data.get("filename", f"file_{idx}"),
                content_type=file_data.get("content_type", "application/octet-stream"),
                size_bytes=len(content),
                entity_id=span.id,
                entity_type="Trace",
                position=idx,
            )
            from rhesis.backend.app.crud import file as file_crud

            file_crud.create_file(db, file_create, organization_id=organization_id)
            total += 1

        logger.info(
            f"[FILE_LINKING] Processed {len(files)} file(s) for "
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

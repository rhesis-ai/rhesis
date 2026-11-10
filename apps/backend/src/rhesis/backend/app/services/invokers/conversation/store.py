"""In-memory conversation history store with TTL.

Provides server-side management of stateless endpoint conversation
histories so that all callers (playground, SDK, Penelope) get a
unified interface: pass ``conversation_id`` to continue a conversation,
omit it to start a new one.

Note:
    This is a process-local store.  In multi-worker deployments each
    worker maintains its own store, so conversations are pinned to
    the worker that created them.  For cross-worker durability,
    replace with a Redis or database-backed implementation.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from rhesis.backend.app.services.invokers.conversation.history import MessageHistoryManager

logger = logging.getLogger(__name__)

# Default TTL: 1 hour
_DEFAULT_TTL_SECONDS = 3600

# Default sweep interval: run every 5 minutes
_DEFAULT_SWEEP_INTERVAL_SECONDS = 300

# (organization_id, project_id) that owns a conversation.
Scope = Tuple[str, str]
_NO_SCOPE: Scope = ("", "")
_Key = Tuple[Scope, str]


def conversation_scope(endpoint: Any) -> Scope:
    """The tenant scope a stateless endpoint's conversations are stored under."""
    organization_id = getattr(endpoint, "organization_id", None)
    project_id = getattr(endpoint, "project_id", None)
    return (str(organization_id or ""), str(project_id or ""))


class ConversationHistoryStore:
    """Thread-safe in-memory store for conversation histories.

    Manages :class:`MessageHistoryManager` instances keyed by
    ``(scope, conversation_id)``, where *scope* is the owning
    ``(organization_id, project_id)``.  A conversation is only reachable
    with the scope it was created under.  Entries are automatically
    evicted after *ttl_seconds* of inactivity (last access).

    All public methods that read or mutate a conversation hold the
    internal lock for the entire operation, so callers never need to
    worry about thread-safety.

    Usage::

        store = ConversationHistoryStore()
        cid = store.create(system_prompt="You are helpful.")
        store.add_user_message(cid, "Hello")
        messages = store.get_messages(cid)
        # -> [{"role": "system", ...}, {"role": "user", ...}]
    """

    def __init__(
        self,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        sweep_interval_seconds: int = _DEFAULT_SWEEP_INTERVAL_SECONDS,
    ) -> None:
        self._histories: Dict[_Key, MessageHistoryManager] = {}
        self._timestamps: Dict[_Key, float] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()

        # Background sweep thread
        self._sweep_interval = sweep_interval_seconds
        self._sweeper: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        if self._sweep_interval > 0:
            self._start_sweeper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, system_prompt: Optional[str] = None, *, scope: Scope = _NO_SCOPE) -> str:
        """Create a new conversation and return its ``conversation_id``."""
        conversation_id = str(uuid4())
        key = (scope, conversation_id)
        with self._lock:
            self._histories[key] = MessageHistoryManager(
                system_prompt=system_prompt,
            )
            self._timestamps[key] = time.monotonic()
        logger.debug(f"Created conversation history: {conversation_id}")
        return conversation_id

    def get(
        self, conversation_id: str, *, scope: Scope = _NO_SCOPE
    ) -> Optional[MessageHistoryManager]:
        """Return the history for *conversation_id*, or ``None`` if expired."""
        with self._lock:
            self._evict_expired()
            return self._touch((scope, conversation_id))

    def exists(self, conversation_id: str, *, scope: Scope = _NO_SCOPE) -> bool:
        """Check whether *conversation_id* has a live (non-expired) history in *scope*."""
        return self.get(conversation_id, scope=scope) is not None

    def add_user_message(
        self, conversation_id: str, content: str, *, scope: Scope = _NO_SCOPE
    ) -> bool:
        """Append a user message.  Returns ``False`` if not found."""
        with self._lock:
            self._evict_expired()
            history = self._touch((scope, conversation_id))
            if history is None:
                return False
            history.add_user_message(content)
        return True

    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        *,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        scope: Scope = _NO_SCOPE,
        **extra: Any,
    ) -> bool:
        """Append an assistant message.  Returns ``False`` if not found."""
        with self._lock:
            self._evict_expired()
            history = self._touch((scope, conversation_id))
            if history is None:
                return False
            history.add_assistant_message(content, tool_calls=tool_calls, **extra)
        return True

    def add_message(
        self, conversation_id: str, message: Dict[str, Any], *, scope: Scope = _NO_SCOPE
    ) -> bool:
        """Append an arbitrary message dict.  Returns ``False`` if not found."""
        with self._lock:
            self._evict_expired()
            history = self._touch((scope, conversation_id))
            if history is None:
                return False
            history.add_message(message)
        return True

    def get_messages(
        self, conversation_id: str, *, scope: Scope = _NO_SCOPE
    ) -> Optional[List[Dict[str, Any]]]:
        """Return all messages for *conversation_id*, or ``None``."""
        with self._lock:
            self._evict_expired()
            history = self._touch((scope, conversation_id))
            if history is None:
                return None
            return history.get_messages()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _touch(self, key: _Key) -> Optional[MessageHistoryManager]:
        """Return the history for *key* and reset its TTL.  Caller holds ``_lock``."""
        history = self._histories.get(key)
        if history is not None:
            self._timestamps[key] = time.monotonic()
        return history

    def _evict_expired(self) -> None:
        """Remove expired entries.  **Must** be called with ``_lock`` held."""
        now = time.monotonic()
        expired = [key for key, ts in self._timestamps.items() if now - ts > self._ttl_seconds]
        for key in expired:
            del self._histories[key]
            del self._timestamps[key]
            logger.debug(f"Evicted expired conversation: {key[1]}")

    def _start_sweeper(self) -> None:
        """Start a daemon thread that periodically evicts expired entries."""
        self._sweeper = threading.Thread(
            target=self._sweep_loop,
            name="conversation-store-sweeper",
            daemon=True,
        )
        self._sweeper.start()

    def _sweep_loop(self) -> None:
        """Background loop: sleep, then evict.  Exits when stop event is set."""
        while not self._stop_event.wait(timeout=self._sweep_interval):
            with self._lock:
                before = len(self._histories)
                self._evict_expired()
                after = len(self._histories)
            evicted = before - after
            if evicted:
                logger.info(f"Sweep: evicted {evicted} expired conversation(s), {after} remaining")

    def shutdown(self) -> None:
        """Stop the background sweeper.  Safe to call multiple times."""
        self._stop_event.set()
        if self._sweeper is not None and self._sweeper.is_alive():
            self._sweeper.join(timeout=2)


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------
_default_store: Optional[ConversationHistoryStore] = None
_store_lock = threading.Lock()


def get_conversation_store() -> ConversationHistoryStore:
    """Return the process-wide :class:`ConversationHistoryStore` singleton."""
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = ConversationHistoryStore()
    return _default_store


def _reset_conversation_store() -> None:
    """Replace the singleton with a fresh instance.  **Test-only.**"""
    global _default_store
    with _store_lock:
        if _default_store is not None:
            _default_store.shutdown()
        _default_store = None

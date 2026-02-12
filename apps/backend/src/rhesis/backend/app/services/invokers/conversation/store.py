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

import threading
import time
from typing import Dict, List, Optional
from uuid import uuid4

from rhesis.backend.logging import logger

from .history import MessageHistoryManager

# Default TTL: 1 hour
_DEFAULT_TTL_SECONDS = 3600

# Default sweep interval: run every 5 minutes
_DEFAULT_SWEEP_INTERVAL_SECONDS = 300


class ConversationHistoryStore:
    """Thread-safe in-memory store for conversation histories.

    Manages :class:`MessageHistoryManager` instances keyed by
    ``conversation_id``.  Entries are automatically evicted after
    *ttl_seconds* of inactivity (last access).

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
        self._histories: Dict[str, MessageHistoryManager] = {}
        self._timestamps: Dict[str, float] = {}
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

    def create(self, system_prompt: Optional[str] = None) -> str:
        """Create a new conversation and return its ``conversation_id``."""
        conversation_id = str(uuid4())
        with self._lock:
            self._histories[conversation_id] = MessageHistoryManager(
                system_prompt=system_prompt,
            )
            self._timestamps[conversation_id] = time.monotonic()
        logger.debug(f"Created conversation history: {conversation_id}")
        return conversation_id

    def get(self, conversation_id: str) -> Optional[MessageHistoryManager]:
        """Return the history for *conversation_id*, or ``None`` if expired."""
        with self._lock:
            self._evict_expired()
            history = self._histories.get(conversation_id)
            if history is not None:
                # Touch -- reset the TTL clock on access
                self._timestamps[conversation_id] = time.monotonic()
            return history

    def exists(self, conversation_id: str) -> bool:
        """Check whether *conversation_id* has a live (non-expired) history."""
        return self.get(conversation_id) is not None

    def add_user_message(self, conversation_id: str, content: str) -> bool:
        """Append a user message.  Returns ``False`` if not found."""
        with self._lock:
            self._evict_expired()
            history = self._histories.get(conversation_id)
            if history is None:
                return False
            self._timestamps[conversation_id] = time.monotonic()
            history.add_user_message(content)
        return True

    def add_assistant_message(self, conversation_id: str, content: str) -> bool:
        """Append an assistant message.  Returns ``False`` if not found."""
        with self._lock:
            self._evict_expired()
            history = self._histories.get(conversation_id)
            if history is None:
                return False
            self._timestamps[conversation_id] = time.monotonic()
            history.add_assistant_message(content)
        return True

    def get_messages(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        """Return all messages for *conversation_id*, or ``None``."""
        with self._lock:
            self._evict_expired()
            history = self._histories.get(conversation_id)
            if history is None:
                return None
            self._timestamps[conversation_id] = time.monotonic()
            return history.get_messages()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        """Remove expired entries.  **Must** be called with ``_lock`` held."""
        now = time.monotonic()
        expired = [cid for cid, ts in self._timestamps.items() if now - ts > self._ttl_seconds]
        for cid in expired:
            del self._histories[cid]
            del self._timestamps[cid]
            logger.debug(f"Evicted expired conversation: {cid}")

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

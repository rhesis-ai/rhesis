"""Tests for ConversationHistoryStore."""

import threading
import time

from rhesis.backend.app.services.invokers.conversation.store import (
    ConversationHistoryStore,
)


class TestConversationHistoryStore:
    """Test ConversationHistoryStore class functionality."""

    def _store(self, **kwargs):
        """Create a store with the sweeper disabled by default."""
        kwargs.setdefault("sweep_interval_seconds", 0)
        return ConversationHistoryStore(**kwargs)

    def test_create_returns_session_id(self):
        """create() returns a non-empty session_id string."""
        store = self._store()
        session_id = store.create()
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_create_unique_ids(self):
        """Each call to create() returns a unique session_id."""
        store = self._store()
        ids = {store.create() for _ in range(50)}
        assert len(ids) == 50

    def test_exists_true_for_live_session(self):
        """exists() returns True for a just-created session."""
        store = self._store()
        sid = store.create()
        assert store.exists(sid) is True

    def test_exists_false_for_unknown(self):
        """exists() returns False for an unknown session_id."""
        store = self._store()
        assert store.exists("does-not-exist") is False

    def test_get_returns_history_for_live_session(self):
        """get() returns a MessageHistoryManager for a live session."""
        store = self._store()
        sid = store.create(system_prompt="Hello")
        history = store.get(sid)
        assert history is not None

    def test_get_returns_none_for_unknown(self):
        """get() returns None for an unknown session_id."""
        store = self._store()
        assert store.get("nope") is None

    def test_add_and_get_messages(self):
        """Messages added via add_user/assistant_message appear in get_messages."""
        store = self._store()
        sid = store.create(system_prompt="Be concise.")

        store.add_user_message(sid, "Hi")
        store.add_assistant_message(sid, "Hello!")
        store.add_user_message(sid, "How are you?")

        messages = store.get_messages(sid)
        assert len(messages) == 4  # system + 2 user + 1 assistant
        assert messages[0] == {"role": "system", "content": "Be concise."}
        assert messages[1] == {"role": "user", "content": "Hi"}
        assert messages[2] == {"role": "assistant", "content": "Hello!"}
        assert messages[3] == {"role": "user", "content": "How are you?"}

    def test_add_user_message_returns_false_for_unknown(self):
        """add_user_message returns False for a missing session."""
        store = self._store()
        assert store.add_user_message("nope", "hello") is False

    def test_add_assistant_message_returns_false_for_unknown(self):
        """add_assistant_message returns False for a missing session."""
        store = self._store()
        assert store.add_assistant_message("nope", "hello") is False

    def test_get_messages_returns_none_for_unknown(self):
        """get_messages returns None for a missing session."""
        store = self._store()
        assert store.get_messages("nope") is None

    def test_create_without_system_prompt(self):
        """Session without system_prompt starts with empty messages."""
        store = self._store()
        sid = store.create()
        store.add_user_message(sid, "Hello")

        messages = store.get_messages(sid)
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    def test_ttl_eviction(self):
        """Sessions are evicted after TTL expires."""
        store = self._store(ttl_seconds=0)
        sid = store.create()

        # Give time for the TTL to expire
        time.sleep(0.01)

        # Access triggers eviction
        assert store.exists(sid) is False
        assert store.get_messages(sid) is None

    def test_independent_sessions(self):
        """Messages in one session do not leak into another."""
        store = self._store()
        sid1 = store.create(system_prompt="Session 1")
        sid2 = store.create(system_prompt="Session 2")

        store.add_user_message(sid1, "Hello from session 1")
        store.add_user_message(sid2, "Hello from session 2")

        msgs1 = store.get_messages(sid1)
        msgs2 = store.get_messages(sid2)

        assert len(msgs1) == 2  # system + user
        assert len(msgs2) == 2
        assert msgs1[1]["content"] == "Hello from session 1"
        assert msgs2[1]["content"] == "Hello from session 2"

    def test_multi_turn_conversation_round_trip(self):
        """Full multi-turn conversation works end-to-end through the store."""
        store = ConversationHistoryStore(sweep_interval_seconds=0)
        sid = store.create(system_prompt="You are a helpful assistant.")

        # Turn 1
        store.add_user_message(sid, "What is 2+2?")
        msgs = store.get_messages(sid)
        assert len(msgs) == 2
        # Simulate endpoint returning "4"
        store.add_assistant_message(sid, "4")

        # Turn 2
        store.add_user_message(sid, "And 3+3?")
        msgs = store.get_messages(sid)
        assert len(msgs) == 4  # system + user + assistant + user
        assert msgs[0]["role"] == "system"
        assert msgs[1] == {"role": "user", "content": "What is 2+2?"}
        assert msgs[2] == {"role": "assistant", "content": "4"}
        assert msgs[3] == {"role": "user", "content": "And 3+3?"}


class TestConversationHistoryStoreSweeper:
    """Test background sweeper functionality."""

    def test_sweeper_starts_by_default(self):
        """The sweeper thread starts when sweep_interval_seconds > 0."""
        store = ConversationHistoryStore(sweep_interval_seconds=60)
        try:
            assert store._sweeper is not None
            assert store._sweeper.is_alive()
            assert store._sweeper.daemon is True
            assert store._sweeper.name == "conversation-store-sweeper"
        finally:
            store.shutdown()

    def test_sweeper_disabled_with_zero_interval(self):
        """No sweeper thread when sweep_interval_seconds=0."""
        store = ConversationHistoryStore(sweep_interval_seconds=0)
        assert store._sweeper is None

    def test_sweeper_evicts_expired_sessions(self):
        """Sweeper removes sessions after TTL expires."""
        store = ConversationHistoryStore(
            ttl_seconds=0,
            sweep_interval_seconds=0.1,
        )
        try:
            sid = store.create(system_prompt="Temp")
            store.add_user_message(sid, "Hello")

            # Session should exist initially
            assert store.exists(sid) is False  # TTL=0, already expired

            # Create another and let sweeper clean it
            sid2 = store.create()
            time.sleep(0.01)  # Let TTL expire

            # Wait for the sweeper to run
            time.sleep(0.25)

            with store._lock:
                assert sid2 not in store._histories
        finally:
            store.shutdown()

    def test_sweeper_preserves_live_sessions(self):
        """Sweeper does not evict sessions that are still within TTL."""
        store = ConversationHistoryStore(
            ttl_seconds=300,
            sweep_interval_seconds=0.1,
        )
        try:
            sid = store.create(system_prompt="Keep me")
            store.add_user_message(sid, "Hello")

            # Wait for at least one sweep cycle
            time.sleep(0.25)

            # Session should still be alive
            assert store.exists(sid) is True
            msgs = store.get_messages(sid)
            assert len(msgs) == 2  # system + user
        finally:
            store.shutdown()

    def test_shutdown_stops_sweeper(self):
        """shutdown() stops the sweeper thread."""
        store = ConversationHistoryStore(sweep_interval_seconds=60)
        assert store._sweeper.is_alive()

        store.shutdown()

        assert not store._sweeper.is_alive()
        assert store._stop_event.is_set()

    def test_shutdown_is_idempotent(self):
        """Calling shutdown() multiple times does not raise."""
        store = ConversationHistoryStore(sweep_interval_seconds=60)
        store.shutdown()
        store.shutdown()  # Should not raise
        assert store._stop_event.is_set()

    def test_sweeper_thread_is_daemon(self):
        """Sweeper thread is a daemon so it doesn't block process exit."""
        store = ConversationHistoryStore(sweep_interval_seconds=60)
        try:
            assert store._sweeper.daemon is True
        finally:
            store.shutdown()

    def test_sweeper_handles_concurrent_access(self):
        """Sweeper doesn't conflict with concurrent store operations."""
        store = ConversationHistoryStore(
            ttl_seconds=300,
            sweep_interval_seconds=0.1,
        )
        errors = []

        def worker(n):
            try:
                for i in range(20):
                    sid = store.create(system_prompt=f"Worker {n}")
                    store.add_user_message(sid, f"msg-{i}")
                    store.get_messages(sid)
                    store.add_assistant_message(sid, f"reply-{i}")
            except Exception as exc:
                errors.append(exc)

        try:
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert errors == [], f"Concurrent errors: {errors}"
        finally:
            store.shutdown()

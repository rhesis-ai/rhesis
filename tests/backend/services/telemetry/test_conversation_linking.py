"""Tests for conversation_linking deferred caches.

Covers both caches:
1. Conversation ID linking (first-turn patching)
2. Mapped output injection (per-turn, before span storage)

Also tests TTL eviction of stale entries and the ConversationLinkingCache
class (Redis mode with mocks, in-memory mode, fallback behaviour).
"""

import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from rhesis.backend.app.services.telemetry.conversation_linking import (
    _CACHE_TTL,
    ConversationLinkingCache,
    PendingConversationLink,
    PendingOutput,
    _cache,
    _evict_stale,
    apply_pending_conversation_links,
    get_trace_id_from_pending_links,
    inject_pending_output,
    register_pending_conversation_link,
    register_pending_output,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Ensure both in-memory caches are empty before and after each test."""
    _cache._pending_links.clear()
    _cache._pending_outputs.clear()
    # Ensure module-level cache uses in-memory mode for unit tests
    orig_redis = _cache._redis
    _cache._redis = None
    yield
    _cache._pending_links.clear()
    _cache._pending_outputs.clear()
    _cache._redis = orig_redis


# ---------------------------------------------------------------
# 1. Conversation ID linking
# ---------------------------------------------------------------


@pytest.mark.unit
class TestRegisterPendingConversationLink:
    """Tests for register_pending_conversation_link()."""

    def test_parks_link_in_cache(self):
        register_pending_conversation_link(
            trace_id="trace-1",
            conversation_id="conv-1",
            organization_id="org-1",
        )

        assert "trace-1" in _cache._pending_links
        entry = _cache._pending_links["trace-1"]
        assert entry.conversation_id == "conv-1"
        assert entry.organization_id == "org-1"

    def test_overwrites_existing_entry(self):
        register_pending_conversation_link("trace-1", "conv-old", "org-1")
        register_pending_conversation_link("trace-1", "conv-new", "org-1")

        assert _cache._pending_links["trace-1"].conversation_id == "conv-new"

    def test_multiple_traces(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")
        register_pending_conversation_link("trace-2", "conv-2", "org-2")

        assert len(_cache._pending_links) == 2


@pytest.mark.unit
class TestApplyPendingConversationLinks:
    """Tests for apply_pending_conversation_links()."""

    def test_applies_matching_link(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        mock_span = Mock()
        mock_span.trace_id = "trace-1"

        mock_db = Mock()
        with (
            patch(
                "rhesis.backend.app.services.telemetry.conversation_linking"
                ".crud.update_conversation_id_for_trace",
                return_value=1,
            ) as mock_update,
            patch(
                "rhesis.backend.app.database.set_session_variables",
            ) as mock_set_vars,
        ):
            total = apply_pending_conversation_links(mock_db, [mock_span])

        assert total == 1
        mock_update.assert_called_once_with(mock_db, "trace-1", "conv-1", "org-1")
        mock_set_vars.assert_called_once_with(mock_db, "org-1", "")

    def test_removes_entry_after_application(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        mock_span = Mock()
        mock_span.trace_id = "trace-1"
        mock_db = Mock()

        with (
            patch(
                "rhesis.backend.app.services.telemetry.conversation_linking"
                ".crud.update_conversation_id_for_trace",
                return_value=1,
            ),
            patch(
                "rhesis.backend.app.database.set_session_variables",
            ),
        ):
            apply_pending_conversation_links(mock_db, [mock_span])

        assert "trace-1" not in _cache._pending_links

    def test_no_match_returns_zero(self):
        register_pending_conversation_link("trace-other", "conv-1", "org-1")

        mock_span = Mock()
        mock_span.trace_id = "trace-unrelated"
        mock_db = Mock()

        total = apply_pending_conversation_links(mock_db, [mock_span])

        assert total == 0
        # The unmatched entry should still be in the cache
        assert "trace-other" in _cache._pending_links

    def test_empty_spans_returns_zero(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        mock_db = Mock()
        total = apply_pending_conversation_links(mock_db, [])

        assert total == 0

    def test_deduplicates_trace_ids(self):
        """Multiple spans with the same trace_id should only trigger one UPDATE."""
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        span_a = Mock()
        span_a.trace_id = "trace-1"
        span_b = Mock()
        span_b.trace_id = "trace-1"

        mock_db = Mock()
        with (
            patch(
                "rhesis.backend.app.services.telemetry.conversation_linking"
                ".crud.update_conversation_id_for_trace",
                return_value=2,
            ) as mock_update,
            patch(
                "rhesis.backend.app.database.set_session_variables",
            ),
        ):
            total = apply_pending_conversation_links(mock_db, [span_a, span_b])

        assert total == 2
        mock_update.assert_called_once()


@pytest.mark.unit
class TestGetTraceIdFromPendingLinks:
    """Tests for get_trace_id_from_pending_links()."""

    def test_returns_trace_id_when_found(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        result = get_trace_id_from_pending_links("conv-1")

        assert result == "trace-1"

    def test_returns_none_when_not_found(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")

        result = get_trace_id_from_pending_links("conv-unknown")

        assert result is None

    def test_returns_none_when_cache_empty(self):
        result = get_trace_id_from_pending_links("conv-1")

        assert result is None

    def test_returns_first_matching_trace_id(self):
        """When multiple traces map to different conversations, return the right one."""
        register_pending_conversation_link("trace-1", "conv-1", "org-1")
        register_pending_conversation_link("trace-2", "conv-2", "org-1")
        register_pending_conversation_link("trace-3", "conv-3", "org-1")

        assert get_trace_id_from_pending_links("conv-2") == "trace-2"

    def test_ignores_stale_entries(self):
        """Stale entries are evicted on register; verify lookup still works."""
        stale_time = time.monotonic() - _CACHE_TTL - 1
        _cache._pending_links["stale-trace"] = PendingConversationLink(
            conversation_id="conv-stale",
            organization_id="org-1",
            registered_at=stale_time,
        )
        # Register a fresh entry, which triggers eviction of stale ones
        register_pending_conversation_link("fresh-trace", "conv-fresh", "org-1")

        assert get_trace_id_from_pending_links("conv-stale") is None
        assert get_trace_id_from_pending_links("conv-fresh") == "fresh-trace"


# ---------------------------------------------------------------
# 2. Mapped output injection
# ---------------------------------------------------------------


@pytest.mark.unit
class TestRegisterPendingOutput:
    """Tests for register_pending_output()."""

    def test_parks_output_in_cache(self):
        register_pending_output("trace-1", "Hello, world!")

        assert "trace-1" in _cache._pending_outputs
        assert _cache._pending_outputs["trace-1"].mapped_output == "Hello, world!"

    def test_overwrites_existing_entry(self):
        register_pending_output("trace-1", "old output")
        register_pending_output("trace-1", "new output")

        assert _cache._pending_outputs["trace-1"].mapped_output == "new output"


@pytest.mark.unit
class TestInjectPendingOutput:
    """Tests for inject_pending_output()."""

    @staticmethod
    def _make_span(
        trace_id="trace-1",
        span_id="span-1",
        parent_span_id=None,
        attributes=None,
    ):
        """Create a minimal span-like object."""
        return SimpleNamespace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            attributes=attributes if attributes is not None else {},
        )

    def test_injects_into_root_span_with_input(self):
        register_pending_output("trace-1", "Mapped output text")

        span = self._make_span(
            attributes={"rhesis.conversation.input": "Hello"},
        )

        count = inject_pending_output([span])

        assert count == 1
        assert span.attributes["rhesis.conversation.output"] == "Mapped output text"

    def test_skips_child_spans(self):
        """Output should only be injected into root spans (no parent)."""
        register_pending_output("trace-1", "Output")

        child_span = self._make_span(
            parent_span_id="parent-123",
            attributes={"rhesis.conversation.input": "Hello"},
        )

        count = inject_pending_output([child_span])

        assert count == 0
        assert "rhesis.conversation.output" not in child_span.attributes

    def test_skips_spans_without_input(self):
        """Spans that don't carry conversation.input should not get output."""
        register_pending_output("trace-1", "Output")

        span = self._make_span(attributes={})

        count = inject_pending_output([span])

        assert count == 0

    def test_does_not_overwrite_existing_output(self):
        """If output is already present, don't overwrite it."""
        register_pending_output("trace-1", "New output")

        span = self._make_span(
            attributes={
                "rhesis.conversation.input": "Hello",
                "rhesis.conversation.output": "Existing output",
            },
        )

        count = inject_pending_output([span])

        assert count == 0
        assert span.attributes["rhesis.conversation.output"] == "Existing output"

    def test_removes_entry_after_injection(self):
        register_pending_output("trace-1", "Output")

        span = self._make_span(
            attributes={"rhesis.conversation.input": "Hello"},
        )

        inject_pending_output([span])

        assert "trace-1" not in _cache._pending_outputs

    def test_no_match_returns_zero(self):
        register_pending_output("trace-other", "Output")

        span = self._make_span(
            trace_id="trace-unrelated",
            attributes={"rhesis.conversation.input": "Hello"},
        )

        count = inject_pending_output([span])

        assert count == 0
        # Unmatched entry should remain
        assert "trace-other" in _cache._pending_outputs

    def test_truncates_output_at_10000_chars(self):
        long_output = "x" * 20000
        register_pending_output("trace-1", long_output)

        span = self._make_span(
            attributes={"rhesis.conversation.input": "Hello"},
        )

        inject_pending_output([span])

        assert len(span.attributes["rhesis.conversation.output"]) == 10000

    def test_multiple_spans_same_trace(self):
        """Only the root span with input gets the output; child spans are skipped."""
        register_pending_output("trace-1", "Output")

        root_span = self._make_span(
            span_id="root",
            attributes={"rhesis.conversation.input": "Hello"},
        )
        child_span = self._make_span(
            span_id="child",
            parent_span_id="root",
            attributes={"rhesis.conversation.input": "Hello"},
        )

        count = inject_pending_output([root_span, child_span])

        assert count == 1
        assert "rhesis.conversation.output" in root_span.attributes
        assert "rhesis.conversation.output" not in child_span.attributes

    def test_empty_spans_returns_zero(self):
        register_pending_output("trace-1", "Output")

        count = inject_pending_output([])

        assert count == 0


# ---------------------------------------------------------------
# TTL eviction
# ---------------------------------------------------------------


@pytest.mark.unit
class TestEvictStale:
    """Tests for _evict_stale() TTL eviction."""

    def test_evicts_stale_entries(self):
        """Entries older than _CACHE_TTL should be removed."""
        stale_time = time.monotonic() - _CACHE_TTL - 1

        _cache._pending_outputs["stale-trace"] = PendingOutput(
            mapped_output="old",
            registered_at=stale_time,
        )
        _cache._pending_outputs["fresh-trace"] = PendingOutput(
            mapped_output="new",
            registered_at=time.monotonic(),
        )

        _evict_stale(_cache._pending_outputs)

        assert "stale-trace" not in _cache._pending_outputs
        assert "fresh-trace" in _cache._pending_outputs

    def test_keeps_fresh_entries(self):
        """Entries within TTL should be kept."""
        _cache._pending_outputs["fresh"] = PendingOutput(
            mapped_output="data",
            registered_at=time.monotonic(),
        )

        _evict_stale(_cache._pending_outputs)

        assert "fresh" in _cache._pending_outputs

    def test_eviction_triggered_on_register(self):
        """Registering a new entry should trigger eviction of stale ones."""
        stale_time = time.monotonic() - _CACHE_TTL - 1
        _cache._pending_outputs["stale"] = PendingOutput(
            mapped_output="old",
            registered_at=stale_time,
        )

        register_pending_output("new-trace", "new output")

        assert "stale" not in _cache._pending_outputs
        assert "new-trace" in _cache._pending_outputs

    def test_eviction_on_conversation_link_register(self):
        """Registering a conversation link should trigger eviction."""
        stale_time = time.monotonic() - _CACHE_TTL - 1
        _cache._pending_links["stale"] = PendingConversationLink(
            conversation_id="conv-old",
            organization_id="org-1",
            registered_at=stale_time,
        )

        register_pending_conversation_link("new-trace", "conv-new", "org-1")

        assert "stale" not in _cache._pending_links
        assert "new-trace" in _cache._pending_links


# ---------------------------------------------------------------
# ConversationLinkingCache class tests
# ---------------------------------------------------------------


@pytest.mark.unit
class TestConversationLinkingCacheInMemory:
    """Tests for ConversationLinkingCache in in-memory mode."""

    def test_initialize_without_redis(self):
        """Cache initializes in memory-only mode when Redis is unavailable."""
        cache = ConversationLinkingCache()
        with patch.dict("os.environ", {"BROKER_URL": "redis://invalid:9999/0"}):
            cache.initialize()

        assert cache._initialized is True
        assert cache._redis is None

    def test_register_and_lookup_link(self):
        """Register a link and look it up by conversation_id."""
        cache = ConversationLinkingCache()
        cache._initialized = True  # skip Redis init

        cache.register_link("trace-1", "conv-1", "org-1")
        result = cache.get_trace_id_for_conversation("conv-1")

        assert result == "trace-1"

    def test_register_and_pop_link(self):
        """Register a link, then pop it by trace_id."""
        cache = ConversationLinkingCache()
        cache._initialized = True

        cache.register_link("trace-1", "conv-1", "org-1")
        matched = cache.pop_links_for_traces(["trace-1", "trace-2"])

        assert len(matched) == 1
        assert matched[0] == ("trace-1", "conv-1", "org-1")
        # Should be removed after pop
        assert cache.get_trace_id_for_conversation("conv-1") is None

    def test_register_and_pop_output(self):
        """Register an output, then pop it by trace_id."""
        cache = ConversationLinkingCache()
        cache._initialized = True

        cache.register_output("trace-1", "Hello output")
        matched = cache.pop_outputs_for_traces(["trace-1"])

        assert matched == {"trace-1": "Hello output"}
        # Should be removed after pop
        assert cache.pop_outputs_for_traces(["trace-1"]) == {}

    def test_output_not_truncated_on_register_inmemory(self):
        """In-memory mode does not truncate on register; truncation is at inject."""
        cache = ConversationLinkingCache()
        cache._initialized = True

        long_output = "x" * 20000
        cache.register_output("trace-1", long_output)

        matched = cache.pop_outputs_for_traces(["trace-1"])
        # In-memory stores the full string; truncation happens at inject time
        assert len(matched["trace-1"]) == 20000


@pytest.mark.unit
class TestConversationLinkingCacheRedis:
    """Tests for ConversationLinkingCache with mocked Redis."""

    @staticmethod
    def _make_cache_with_redis():
        """Create a cache instance with a mocked Redis client."""
        cache = ConversationLinkingCache()
        cache._initialized = True
        cache._redis = MagicMock()
        return cache

    def test_register_link_writes_to_redis(self):
        cache = self._make_cache_with_redis()
        pipe = MagicMock()
        cache._redis.pipeline.return_value = pipe

        cache.register_link("trace-1", "conv-1", "org-1")

        cache._redis.pipeline.assert_called_once()
        assert pipe.set.call_count == 2

        # Verify the pending key
        pending_call = pipe.set.call_args_list[0]
        assert pending_call[0][0] == "convlink:pending:trace-1"
        payload = json.loads(pending_call[0][1])
        assert payload == {
            "conversation_id": "conv-1",
            "organization_id": "org-1",
        }

        # Verify the reverse key
        reverse_call = pipe.set.call_args_list[1]
        assert reverse_call[0][0] == "convlink:reverse:conv-1"
        assert reverse_call[0][1] == "trace-1"

        pipe.execute.assert_called_once()

    def test_get_trace_id_reads_from_redis(self):
        cache = self._make_cache_with_redis()
        cache._redis.get.return_value = "trace-1"

        result = cache.get_trace_id_for_conversation("conv-1")

        assert result == "trace-1"
        cache._redis.get.assert_called_once_with("convlink:reverse:conv-1")

    def test_get_trace_id_returns_none_for_miss(self):
        cache = self._make_cache_with_redis()
        cache._redis.get.return_value = None

        result = cache.get_trace_id_for_conversation("conv-unknown")

        assert result is None

    def test_pop_links_fetches_and_deletes_redis_keys(self):
        cache = self._make_cache_with_redis()
        payload = json.dumps({"conversation_id": "conv-1", "organization_id": "org-1"})
        cache._redis.mget.return_value = [payload, None]

        matched = cache.pop_links_for_traces(["trace-1", "trace-2"])

        assert len(matched) == 1
        assert matched[0] == ("trace-1", "conv-1", "org-1")
        cache._redis.delete.assert_called_once_with(
            "convlink:pending:trace-1",
            "convlink:reverse:conv-1",
        )

    def test_register_output_writes_to_redis(self):
        cache = self._make_cache_with_redis()

        cache.register_output("trace-1", "Hello output")

        cache._redis.set.assert_called_once_with(
            "convlink:output:trace-1",
            "Hello output",
            ex=120,
        )

    def test_register_output_truncates_at_10000(self):
        cache = self._make_cache_with_redis()

        long_output = "x" * 20000
        cache.register_output("trace-1", long_output)

        stored_value = cache._redis.set.call_args[0][1]
        assert len(stored_value) == 10000

    def test_pop_outputs_fetches_and_deletes_redis_keys(self):
        cache = self._make_cache_with_redis()
        cache._redis.mget.return_value = ["Output text", None]

        matched = cache.pop_outputs_for_traces(["trace-1", "trace-2"])

        assert matched == {"trace-1": "Output text"}
        cache._redis.delete.assert_called_once_with("convlink:output:trace-1")

    def test_redis_failure_falls_back_to_memory(self):
        """When Redis raises an exception, operations fall back to in-memory."""
        cache = self._make_cache_with_redis()
        cache._redis.pipeline.side_effect = ConnectionError("Redis down")

        # Should not raise — falls back to memory
        cache.register_link("trace-1", "conv-1", "org-1")

        assert "trace-1" in cache._pending_links
        assert cache._pending_links["trace-1"].conversation_id == "conv-1"

    def test_redis_read_failure_falls_back_to_memory(self):
        """When Redis GET fails, reverse lookup falls back to in-memory."""
        cache = self._make_cache_with_redis()
        # Pre-populate memory cache
        cache._pending_links["trace-1"] = PendingConversationLink(
            conversation_id="conv-1",
            organization_id="org-1",
            registered_at=time.monotonic(),
        )
        cache._redis.get.side_effect = ConnectionError("Redis down")

        result = cache.get_trace_id_for_conversation("conv-1")

        assert result == "trace-1"

    def test_close_closes_redis(self):
        cache = self._make_cache_with_redis()

        cache.close()

        cache._redis is None  # noqa: B015

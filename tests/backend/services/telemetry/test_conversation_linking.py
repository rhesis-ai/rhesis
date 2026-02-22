"""Tests for conversation_linking deferred caches.

Covers both caches:
1. Conversation ID linking (first-turn patching)
2. Mapped output injection (per-turn, before span storage)

Also tests TTL eviction of stale entries.
"""

import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from rhesis.backend.app.services.telemetry.conversation_linking import (
    _CACHE_TTL,
    _evict_stale,
    _pending_conversation_links,
    _pending_outputs,
    apply_pending_conversation_links,
    inject_pending_output,
    register_pending_conversation_link,
    register_pending_output,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Ensure both caches are empty before and after each test."""
    _pending_conversation_links.clear()
    _pending_outputs.clear()
    yield
    _pending_conversation_links.clear()
    _pending_outputs.clear()


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

        assert "trace-1" in _pending_conversation_links
        entry = _pending_conversation_links["trace-1"]
        assert entry.conversation_id == "conv-1"
        assert entry.organization_id == "org-1"

    def test_overwrites_existing_entry(self):
        register_pending_conversation_link("trace-1", "conv-old", "org-1")
        register_pending_conversation_link("trace-1", "conv-new", "org-1")

        assert _pending_conversation_links["trace-1"].conversation_id == "conv-new"

    def test_multiple_traces(self):
        register_pending_conversation_link("trace-1", "conv-1", "org-1")
        register_pending_conversation_link("trace-2", "conv-2", "org-2")

        assert len(_pending_conversation_links) == 2


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

        assert "trace-1" not in _pending_conversation_links

    def test_no_match_returns_zero(self):
        register_pending_conversation_link("trace-other", "conv-1", "org-1")

        mock_span = Mock()
        mock_span.trace_id = "trace-unrelated"
        mock_db = Mock()

        total = apply_pending_conversation_links(mock_db, [mock_span])

        assert total == 0
        # The unmatched entry should still be in the cache
        assert "trace-other" in _pending_conversation_links

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


# ---------------------------------------------------------------
# 2. Mapped output injection
# ---------------------------------------------------------------


@pytest.mark.unit
class TestRegisterPendingOutput:
    """Tests for register_pending_output()."""

    def test_parks_output_in_cache(self):
        register_pending_output("trace-1", "Hello, world!")

        assert "trace-1" in _pending_outputs
        assert _pending_outputs["trace-1"].mapped_output == "Hello, world!"

    def test_overwrites_existing_entry(self):
        register_pending_output("trace-1", "old output")
        register_pending_output("trace-1", "new output")

        assert _pending_outputs["trace-1"].mapped_output == "new output"


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

        assert "trace-1" not in _pending_outputs

    def test_no_match_returns_zero(self):
        register_pending_output("trace-other", "Output")

        span = self._make_span(
            trace_id="trace-unrelated",
            attributes={"rhesis.conversation.input": "Hello"},
        )

        count = inject_pending_output([span])

        assert count == 0
        # Unmatched entry should remain
        assert "trace-other" in _pending_outputs

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

        # Simulate a stale entry by directly inserting with an old timestamp
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            PendingOutput,
        )

        _pending_outputs["stale-trace"] = PendingOutput(
            mapped_output="old",
            registered_at=stale_time,
        )
        _pending_outputs["fresh-trace"] = PendingOutput(
            mapped_output="new",
            registered_at=time.monotonic(),
        )

        _evict_stale(_pending_outputs)

        assert "stale-trace" not in _pending_outputs
        assert "fresh-trace" in _pending_outputs

    def test_keeps_fresh_entries(self):
        """Entries within TTL should be kept."""
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            PendingOutput,
        )

        _pending_outputs["fresh"] = PendingOutput(
            mapped_output="data",
            registered_at=time.monotonic(),
        )

        _evict_stale(_pending_outputs)

        assert "fresh" in _pending_outputs

    def test_eviction_triggered_on_register(self):
        """Registering a new entry should trigger eviction of stale ones."""
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            PendingOutput,
        )

        stale_time = time.monotonic() - _CACHE_TTL - 1
        _pending_outputs["stale"] = PendingOutput(
            mapped_output="old",
            registered_at=stale_time,
        )

        register_pending_output("new-trace", "new output")

        assert "stale" not in _pending_outputs
        assert "new-trace" in _pending_outputs

    def test_eviction_on_conversation_link_register(self):
        """Registering a conversation link should trigger eviction."""
        from rhesis.backend.app.services.telemetry.conversation_linking import (
            PendingConversationLink,
        )

        stale_time = time.monotonic() - _CACHE_TTL - 1
        _pending_conversation_links["stale"] = PendingConversationLink(
            conversation_id="conv-old",
            organization_id="org-1",
            registered_at=stale_time,
        )

        register_pending_conversation_link("new-trace", "conv-new", "org-1")

        assert "stale" not in _pending_conversation_links
        assert "new-trace" in _pending_conversation_links

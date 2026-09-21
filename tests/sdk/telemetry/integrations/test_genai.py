"""Tests for the framework-neutral GenAI helpers in ``genai.py``.

These back the Microsoft Agent Framework and Google ADK integrations, which read
a turn's text back from a per-trace store when the run root is exported. The
store's release policy is the delicate part: too eager and one exporter starves
the others, too lazy and a long-running process sits on megabytes of text.
"""

import pytest
from rhesis.telemetry import conversation as rhesis_conversation
from rhesis.telemetry.conversation import anchor_conversation, get_conversation_anchor

from rhesis.sdk.telemetry.integrations.genai import (
    ConversationTraceRegistry,
    DeferredReleaseQueue,
)


@pytest.fixture
def stores() -> tuple[dict, dict]:
    """Two trace-keyed stores, the shape an integration registry keeps."""
    return {}, {}


class TestHasEntries:
    def test_reports_content_in_any_store(self, stores):
        first, second = stores
        queue = DeferredReleaseQueue(first, second)

        assert queue.has_entries(1) is False
        second[1] = "only in the second store"
        assert queue.has_entries(1) is True

    def test_a_store_is_held_by_reference(self, stores):
        """The owner records into its own dicts after building the queue."""
        first, _second = stores
        queue = DeferredReleaseQueue(*stores)

        first[7] = "recorded later"

        assert queue.has_entries(7) is True


class TestQueueRelease:
    def test_a_read_does_not_free_the_entry(self, stores):
        """The other wrapped exporters still have to find it."""
        first, _second = stores
        first[1] = "content"
        queue = DeferredReleaseQueue(*stores, max_served=4)

        queue.queue_release(1)

        assert first[1] == "content"

    def test_entries_are_freed_once_enough_traces_follow(self, stores):
        first, second = stores
        queue = DeferredReleaseQueue(*stores, max_served=2)
        for trace_id in (1, 2, 3):
            first[trace_id] = f"in-{trace_id}"
            second[trace_id] = f"out-{trace_id}"

        for trace_id in (1, 2, 3):
            queue.queue_release(trace_id)

        assert 1 not in first and 1 not in second, "the oldest read is freed"
        assert 2 in first and 3 in first, "the two most recent are kept"

    def test_every_store_is_freed(self, stores):
        """A store left out of the release loop grows on its own."""
        first, second = stores
        queue = DeferredReleaseQueue(*stores, max_served=1)
        for trace_id in (1, 2):
            first[trace_id] = "in"
            second[trace_id] = "out"

        queue.queue_release(1)
        queue.queue_release(2)

        assert 1 not in first
        assert 1 not in second

    def test_re_reading_moves_an_entry_back_to_the_newest(self, stores):
        """A second exporter reading a trace should buy it more time, not none.

        Re-inserting a key a dict already holds leaves its position alone, so
        without the explicit removal first, the re-read counts for nothing and
        the trace is freed on the same schedule as if it had been read once.
        """
        first, _second = stores
        queue = DeferredReleaseQueue(*stores, max_served=2)
        for trace_id in (1, 2, 3):
            first[trace_id] = f"content-{trace_id}"

        queue.queue_release(1)
        queue.queue_release(2)
        queue.queue_release(1)  # trace 1 read again, so it is the newest now
        queue.queue_release(3)

        assert first.get(1) == "content-1", "the re-read trace should have survived"
        assert 2 not in first, "trace 2 was the oldest read, so it goes"

    def test_a_trace_with_nothing_recorded_takes_no_slot(self, stores):
        """Otherwise content-free traces evict the ones carrying content."""
        first, _second = stores
        queue = DeferredReleaseQueue(*stores, max_served=1)
        first[1] = "content"
        queue.queue_release(1)

        for empty in range(2, 20):
            queue.queue_release(empty)

        assert first[1] == "content"


class TestClear:
    def test_empties_the_queue_and_the_stores(self, stores):
        first, second = stores
        queue = DeferredReleaseQueue(*stores, max_served=8)
        first[1] = "in"
        second[1] = "out"
        queue.queue_release(1)

        queue.clear()

        assert first == {} and second == {}
        # Nothing is still queued, so a later trace is not freed early.
        first[2] = "in"
        queue.queue_release(2)
        assert first[2] == "in"


class TestConversationTraceRegistryUsesTheSharedAnchor:
    """The join has to agree with every other mechanism on one anchor.

    ``conversation_turn``, ``@endpoint``/``@observe``, LangGraph and Haystack all
    anchor a conversation in the store in ``rhesis.telemetry.conversation``. This
    registry used to keep its own, so a conversation whose turns alternated
    between the two arrived as two traces under one id.
    """

    @pytest.fixture(autouse=True)
    def forget_shared_anchors(self):
        rhesis_conversation._anchors.clear()
        yield
        rhesis_conversation._anchors.clear()

    def test_the_first_claim_anchors_in_the_shared_store(self):
        """So the other mechanisms join this trace rather than inventing one."""
        registry = ConversationTraceRegistry()

        registry.claim(0xA1, "conv-1")

        assert get_conversation_anchor("conv-1") == format(0xA1, "032x")
        assert registry.target(0xA1) is None, "the anchor turn is never rewritten"

    def test_a_turn_joins_an_anchor_another_mechanism_wrote(self):
        """The bug: ``conversation_turn`` ran turn one, a framework run is turn two."""
        anchor_conversation("conv-1", format(0xA1, "032x"))
        registry = ConversationTraceRegistry()

        registry.claim(0xB2, "conv-1")

        assert registry.target(0xB2) == 0xA1

    def test_another_mechanism_joins_an_anchor_the_registry_wrote(self):
        """The mirror: a framework run went first."""
        registry = ConversationTraceRegistry()
        registry.claim(0xA1, "conv-1")

        # What conversation_turn reads when it opens the next turn.
        assert get_conversation_anchor("conv-1") == format(0xA1, "032x")

    def test_the_store_decides_who_anchors(self):
        """First writer wins there, so a second claim for a fresh conversation
        does not overwrite it and is rewritten onto it instead."""
        registry = ConversationTraceRegistry()
        registry.claim(0xA1, "conv-1")
        registry.claim(0xB2, "conv-1")

        assert get_conversation_anchor("conv-1") == format(0xA1, "032x")
        assert registry.target(0xB2) == 0xA1

    def test_a_poisoned_anchor_is_not_used(self):
        """An all-zero trace id is not a trace anything can be written to."""
        anchor_conversation("conv-zero", "0" * 32)
        registry = ConversationTraceRegistry()

        registry.claim(0xB2, "conv-zero")

        assert registry.target(0xB2) is None

    def test_no_conversation_id_anchors_nothing(self):
        registry = ConversationTraceRegistry()

        registry.claim(0xA1, None)

        assert registry.target(0xA1) is None
        assert rhesis_conversation._anchors._anchors == {}

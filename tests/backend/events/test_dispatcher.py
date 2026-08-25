"""Dispatcher delivery policy: what a sink failure means, and that redaction
runs once centrally rather than per sink. See events-layer.md's "delivery
policy" section for the contract this pins.

``dispatcher._sinks`` is module-level state that ``events/__init__.py``
already seeded with the real ``ActivityLogSink`` at import time, so every
test here saves and restores it rather than mutating the shared list.
"""

import pytest

from rhesis.backend.events import dispatcher
from rhesis.backend.events.types import PlatformEvent
from tests.backend.events._helpers import make_event


@pytest.fixture(autouse=True)
def isolated_sinks():
    """Swap in an empty registry for the duration of each test."""
    original = dispatcher._sinks
    dispatcher._sinks = []
    try:
        yield
    finally:
        dispatcher._sinks = original


class _RecordingSink:
    def __init__(self, name="recording", critical=False, raises=None, handles_result=True):
        self.name = name
        self.critical = critical
        self._raises = raises
        self._handles_result = handles_result
        self.received = []

    def handles(self, event: PlatformEvent) -> bool:
        return self._handles_result

    def deliver(self, event: PlatformEvent, db) -> None:
        if self._raises is not None:
            raise self._raises
        self.received.append(event)


class TestSinkFailurePolicy:
    def test_non_critical_sink_raising_does_not_propagate(self):
        sink = _RecordingSink(raises=RuntimeError("boom"), critical=False)
        dispatcher.register_sink(sink)

        dispatcher.emit(make_event())  # must not raise

    def test_non_critical_sink_raising_does_not_stop_later_sinks(self):
        failing = _RecordingSink(name="failing", raises=RuntimeError("boom"), critical=False)
        healthy = _RecordingSink(name="healthy")
        dispatcher.register_sink(failing)
        dispatcher.register_sink(healthy)

        event = make_event()
        dispatcher.emit(event)

        assert healthy.received == [event]

    def test_critical_sink_raising_propagates(self):
        sink = _RecordingSink(raises=RuntimeError("compliance gap"), critical=True)
        dispatcher.register_sink(sink)

        with pytest.raises(RuntimeError, match="compliance gap"):
            dispatcher.emit(make_event())

    def test_a_critical_sink_requiring_db_raises_when_none_is_given(self):
        """Stands in for a future AuditSink: critical=True, and it fails
        closed rather than writing something it cannot make atomic."""

        class _AuditLikeSink:
            name = "audit-like"
            critical = True

            def handles(self, event):
                return True

            def deliver(self, event, db):
                if db is None:
                    raise ValueError("audit sink requires a session")

        dispatcher.register_sink(_AuditLikeSink())

        with pytest.raises(ValueError, match="requires a session"):
            dispatcher.emit(make_event())  # no db= passed

    def test_sinks_not_handling_the_event_are_never_delivered_to(self):
        sink = _RecordingSink(handles_result=False)
        dispatcher.register_sink(sink)

        dispatcher.emit(make_event())

        assert sink.received == []


class TestRedactionRunsOnce:
    def test_context_is_redacted_before_any_sink_sees_it(self):
        first = _RecordingSink(name="first")
        second = _RecordingSink(name="second")
        dispatcher.register_sink(first)
        dispatcher.register_sink(second)

        event = make_event(context={"password": "secret", "keep": "x"})
        dispatcher.emit(event)

        for sink in (first, second):
            assert len(sink.received) == 1
            assert sink.received[0].context == {"keep": "x"}, (
                "every sink must see the same already-redacted event, not do its own redaction"
            )

    def test_original_event_object_is_not_mutated(self):
        """PlatformEvent is frozen -- redaction must return a copy, not
        mutate in place, so a caller holding a reference to the event they
        built does not see it silently change underneath them."""
        sink = _RecordingSink()
        dispatcher.register_sink(sink)

        event = make_event(context={"password": "secret"})
        dispatcher.emit(event)

        assert event.context == {"password": "secret"}

    def test_no_context_skips_the_copy(self):
        sink = _RecordingSink()
        dispatcher.register_sink(sink)

        event = make_event()
        dispatcher.emit(event)

        assert sink.received[0] is event, "an event with nothing to redact is passed through as-is"

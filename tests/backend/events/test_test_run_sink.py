"""TestRunSink: coalesces test_run.progressed ticks and publishes to
test_run:{entity_id} with no database session. Timers are not awaited in
real time -- ``_flush`` is called directly, since the sink's own coalescing
window is an implementation detail these tests don't need to wait out.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType
from rhesis.backend.events.sinks.test_run import TestRunSink
from rhesis.backend.events.types import ActivityLogged, TestRunProgressed

_PATCH_TARGET = "rhesis.backend.events.sinks.test_run.publish_event"


def _progressed(**overrides) -> TestRunProgressed:
    fields = dict(
        occurred_at=datetime.now(timezone.utc),
        organization_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        source="test",
        entity_type="test_run",
        entity_id=uuid4(),
        completed=1,
        total=10,
    )
    fields.update(overrides)
    return TestRunProgressed(**fields)


class TestTestRunSinkHandles:
    def test_handles_only_test_run_progressed(self):
        sink = TestRunSink()
        assert sink.handles(_progressed())
        assert not sink.handles(
            ActivityLogged(
                occurred_at=datetime.now(timezone.utc),
                organization_id=uuid4(),
                trace_id="a" * 32,
                span_id="b" * 16,
                source="test",
                level="info",
                message="hi",
            )
        )


class TestTestRunSinkDeliver:
    def test_no_db_session_opened(self):
        """The whole point of this sink over WebSocketSink: no DB lookup."""
        sink = TestRunSink()
        event = _progressed()

        with (
            patch(_PATCH_TARGET) as mock_publish,
            patch("rhesis.backend.events.sinks.test_run.threading.Timer") as mock_timer_cls,
        ):
            sink.deliver(event, db=None)
            sink._flush(str(event.entity_id))

        mock_publish.assert_called_once()
        # Confirms nothing under this sink ever touches a Session -- deliver()
        # takes db=None and never dereferences it.
        assert mock_timer_cls.called

    def test_publishes_to_test_run_channel(self):
        sink = TestRunSink()
        event = _progressed(completed=3, total=10)

        with patch(_PATCH_TARGET) as mock_publish:
            sink.deliver(event, db=None)
            sink._flush(str(event.entity_id))

        message, target = mock_publish.call_args.args
        assert isinstance(target, ChannelTarget)
        assert target.channel == f"test_run:{event.entity_id}"
        assert message.type == EventType.TEST_RUN_PROGRESSED
        assert message.payload["completed"] == 3
        assert message.payload["total"] == 10
        assert message.payload["generating_test_ids"] == []
        assert message.payload["evaluating_test_ids"] == []

    def test_no_entity_id_publishes_nothing(self):
        sink = TestRunSink()
        event = _progressed(entity_id=None)

        with patch(_PATCH_TARGET) as mock_publish:
            sink.deliver(event, db=None)

        mock_publish.assert_not_called()

    def test_coalesces_rapid_events_for_same_run(self):
        """Two rapid deliver() calls for one entity_id produce one publish,
        of the latest event -- deliver() overwrites _pending, it doesn't queue.
        """
        sink = TestRunSink()
        entity_id = uuid4()
        first = _progressed(entity_id=entity_id, completed=1, total=10)
        second = _progressed(entity_id=entity_id, completed=2, total=10)

        with (
            patch(_PATCH_TARGET) as mock_publish,
            patch("rhesis.backend.events.sinks.test_run.threading.Timer"),
        ):
            sink.deliver(first, db=None)
            sink.deliver(second, db=None)
            sink._flush(str(entity_id))

        mock_publish.assert_called_once()
        message, _ = mock_publish.call_args.args
        assert message.payload["completed"] == 2

    def test_separate_runs_not_coalesced(self):
        sink = TestRunSink()
        event_a = _progressed()
        event_b = _progressed()

        with (
            patch(_PATCH_TARGET) as mock_publish,
            patch("rhesis.backend.events.sinks.test_run.threading.Timer"),
        ):
            sink.deliver(event_a, db=None)
            sink.deliver(event_b, db=None)
            sink._flush(str(event_a.entity_id))
            sink._flush(str(event_b.entity_id))

        assert mock_publish.call_count == 2
        channels = {call.args[1].channel for call in mock_publish.call_args_list}
        assert channels == {f"test_run:{event_a.entity_id}", f"test_run:{event_b.entity_id}"}

    def test_flush_with_nothing_pending_publishes_nothing(self):
        sink = TestRunSink()
        with patch(_PATCH_TARGET) as mock_publish:
            sink._flush(str(uuid4()))
        mock_publish.assert_not_called()

    def test_publish_failure_is_swallowed(self):
        sink = TestRunSink()
        event = _progressed()

        with (
            patch(_PATCH_TARGET, side_effect=RuntimeError("redis down")),
            patch("rhesis.backend.events.sinks.test_run.threading.Timer"),
        ):
            sink.deliver(event, db=None)
            sink._flush(str(event.entity_id))  # must not raise

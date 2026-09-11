"""Events that already carry ``job_id`` cost the sinks no lookup session.

Before this, every ActivityLogged event from a worker cost two sessions on
top of the write itself: ActivityLogSink and WebSocketSink each resolved the
``job`` row from ``celery_task_id`` on a session of their own. With the id on
the event, WebSocketSink opens nothing and ActivityLogSink only opens the one
it writes on -- or none at all when the caller lends it a session.

Session opens are counted by patching ``get_db_with_tenant_variables`` in
each sink's module, which is the only way either sink gets a connection.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from rhesis.backend.events.sinks.activity_log import ActivityLogSink
from rhesis.backend.events.sinks.websocket import WebSocketSink
from rhesis.backend.events.types import ActivityLogged, JobStarted
from tests.backend.fixtures.test_setup import create_test_organization_and_user

_AL_SESSIONS = "rhesis.backend.events.sinks.activity_log.get_db_with_tenant_variables"
_WS_SESSIONS = "rhesis.backend.events.sinks.websocket.get_db_with_tenant_variables"
_WS_PUBLISH = "rhesis.backend.events.sinks.websocket.publish_event"


def _base(**overrides):
    fields = dict(
        occurred_at=datetime.now(timezone.utc),
        organization_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        source="test",
        celery_task_id="task-with-job-id",
    )
    fields.update(overrides)
    return fields


def _job_row(db: Session, org, user, celery_task_id: str) -> Job:
    job = Job(
        organization_id=org.id,
        user_id=user.id,
        celery_task_id=celery_task_id,
        job_type="test.job",
        status="running",
    )
    db.add(job)
    db.flush()
    return job


class TestWebSocketSinkWithJobId:
    def test_opens_no_session_and_publishes_to_the_job_channel(self):
        job_id = uuid4()
        event = JobStarted(**_base(job_id=job_id))

        with (
            patch(_WS_SESSIONS) as mock_sessions,
            patch(_WS_PUBLISH) as mock_publish,
        ):
            WebSocketSink().deliver(event, db=None)

        mock_sessions.assert_not_called()
        assert mock_publish.call_count == 2
        _, target = mock_publish.call_args_list[0].args
        assert target.channel == f"job:{job_id}"

    def test_without_job_id_still_falls_back_to_the_lookup(self):
        """Callers that never learned the id (a message queued before the
        header existed) keep working through the old celery_task_id path."""
        event = ActivityLogged(**_base(level="info", message="hi"))
        assert event.job_id is None

        with (
            patch(_WS_SESSIONS) as mock_sessions,
            patch(_WS_PUBLISH) as mock_publish,
        ):
            mock_sessions.return_value.__enter__.return_value = object()
            with patch(
                "rhesis.backend.events.sinks.websocket.get_job_by_celery_task_id",
                return_value=None,
            ) as mock_lookup:
                WebSocketSink().deliver(event, db=None)

        mock_sessions.assert_called_once()
        mock_lookup.assert_called_once()
        mock_publish.assert_not_called()


class TestActivityLogSinkWithJobId:
    def test_joins_the_callers_session_and_opens_none_of_its_own(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Sink JobId Org", "sinkjobid@events-test.com", "Sink User"
        )
        job = _job_row(test_db, org, user, "task-with-job-id")
        event = ActivityLogged(
            **_base(organization_id=org.id, user_id=user.id, job_id=job.id),
            level="info",
            message="Test 1/3 succeeded",
        )

        with patch(_AL_SESSIONS) as mock_sessions:
            ActivityLogSink().deliver(event, db=test_db)

        mock_sessions.assert_not_called()
        entry = test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).one()
        assert entry.message == "Test 1/3 succeeded"
        assert entry.sequence == 1

    def test_joining_flushes_but_does_not_commit(self, test_db: Session):
        """The dispatcher promises "join the caller's transaction": the
        caller keeps the commit, and their unrelated pending work with it."""
        org, user, _ = create_test_organization_and_user(
            test_db, "Sink Flush Org", "sinkflush@events-test.com", "Sink User"
        )
        job = _job_row(test_db, org, user, "task-with-job-id")
        event = ActivityLogged(
            **_base(organization_id=org.id, user_id=user.id, job_id=job.id),
            level="info",
            message="joined",
        )

        with patch.object(test_db, "commit") as mock_commit:
            ActivityLogSink().deliver(event, db=test_db)

        mock_commit.assert_not_called()
        assert test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).count() == 1

    def test_uses_the_stamped_job_id_without_looking_it_up(self, test_db: Session):
        """A stamped id wins even when celery_task_id would resolve to nothing
        -- proving the lookup was skipped, not just that it agreed."""
        org, user, _ = create_test_organization_and_user(
            test_db, "Sink Stamp Org", "sinkstamp@events-test.com", "Sink User"
        )
        job = _job_row(test_db, org, user, "some-other-celery-id")
        event = ActivityLogged(
            **_base(
                organization_id=org.id,
                user_id=user.id,
                job_id=job.id,
                celery_task_id="no-such-task",
            ),
            level="warning",
            message="stamped",
        )

        ActivityLogSink().deliver(event, db=test_db)

        entry = test_db.query(ActivityLog).filter(ActivityLog.job_id == job.id).one()
        assert entry.level == "warning"

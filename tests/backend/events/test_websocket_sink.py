"""WebSocketSink: resolves job_id from celery_task_id and publishes to the
job's channel. Mirrors test_launch_job_queued_event.py's use of
``real_commit_test_db`` since the sink opens its own connection, same
cross-connection-visibility reason as ActivityLogSink.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from rhesis.backend.app.models.job import Job
from rhesis.backend.app.schemas.websocket import ChannelTarget, EventType
from rhesis.backend.events.sinks.websocket import WebSocketSink
from rhesis.backend.events.types import (
    ActivityLogged,
    JobFailed,
    JobQueued,
    JobRetried,
    JobStarted,
)
from tests.backend.events._helpers import make_event
from tests.backend.fixtures.test_setup import create_test_organization_and_user

_PATCH_TARGET = "rhesis.backend.events.sinks.websocket.publish_event"


def _job_row(db: Session, org, user, celery_task_id: str) -> Job:
    job = Job(
        organization_id=org.id,
        user_id=user.id,
        celery_task_id=celery_task_id,
        job_type="test.job",
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _base(**overrides):
    fields = dict(
        occurred_at=datetime.now(timezone.utc),
        organization_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        source="test",
    )
    fields.update(overrides)
    return fields


class TestWebSocketSinkHandles:
    def test_handles_lifecycle_and_activity_events(self):
        sink = WebSocketSink()
        assert sink.handles(JobQueued(**_base(), job_type="x"))
        assert sink.handles(make_event())

    def test_does_not_handle_unknown_event(self):
        class _Other:
            pass

        assert not WebSocketSink().handles(_Other())


class TestWebSocketSinkDeliver:
    def test_publishes_activity_and_status_for_a_lifecycle_event(
        self, real_commit_test_db: Session
    ):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org", "wssink@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()
        job = _job_row(db, org, user, celery_task_id="ws-sink-task-1")

        event = JobStarted(
            **_base(
                organization_id=org.id,
                user_id=user.id,
                celery_task_id="ws-sink-task-1",
            )
        )

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        assert mock_publish.call_count == 2
        activity_call, status_call = mock_publish.call_args_list
        activity_message, activity_target = activity_call.args
        status_message, status_target = status_call.args

        assert isinstance(activity_target, ChannelTarget)
        assert activity_target.channel == f"job:{job.id}"
        assert activity_message.type == EventType.JOB_ACTIVITY_APPENDED
        assert activity_message.payload == {"level": "info", "message": "Job started"}

        assert status_target.channel == f"job:{job.id}"
        assert status_message.type == EventType.JOB_STATUS_CHANGED
        assert status_message.payload == {"status": "running"}

    def test_activity_logged_uses_its_own_level_and_message(self, real_commit_test_db: Session):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org 2", "wssink2@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()
        job = _job_row(db, org, user, celery_task_id="ws-sink-task-2")

        event = ActivityLogged(
            **_base(
                organization_id=org.id,
                user_id=user.id,
                celery_task_id="ws-sink-task-2",
                level="warning",
                message="Retrying step 2",
            )
        )

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        # ActivityLogged has no mapped status transition, so only the
        # activity push happens -- no JOB_STATUS_CHANGED message.
        assert mock_publish.call_count == 1
        message, target = mock_publish.call_args.args
        assert target.channel == f"job:{job.id}"
        assert message.payload == {"level": "warning", "message": "Retrying step 2"}

    def test_no_celery_task_id_publishes_nothing(self, real_commit_test_db: Session):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org 3", "wssink3@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()

        event = make_event(organization_id=org.id, user_id=user.id)
        assert event.celery_task_id is None

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        mock_publish.assert_not_called()

    def test_unknown_celery_task_id_publishes_nothing(self, real_commit_test_db: Session):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org 4", "wssink4@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()

        event = make_event(organization_id=org.id, user_id=user.id, celery_task_id="no-such-task")

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        mock_publish.assert_not_called()


class TestWebSocketSinkStatusPush:
    def test_job_retried_still_pushes_a_status_message(self, real_commit_test_db: Session):
        """tracking.mark_retrying leaves status at running and moves only the
        attempt counter, which the detail header also shows -- so a retry must
        still push the job-row message, or the displayed attempt goes stale.
        """
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org 6", "wssink6@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()
        job = _job_row(db, org, user, celery_task_id="ws-sink-task-6")

        event = JobRetried(
            **_base(
                organization_id=org.id,
                user_id=user.id,
                celery_task_id="ws-sink-task-6",
                attempt=2,
            )
        )

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        assert mock_publish.call_count == 2
        activity_message, _ = mock_publish.call_args_list[0].args
        status_message, status_target = mock_publish.call_args_list[1].args

        assert activity_message.payload == {
            "level": "warning",
            "message": "Retrying (attempt 2)",
        }
        assert status_target.channel == f"job:{job.id}"
        assert status_message.type == EventType.JOB_STATUS_CHANGED
        assert status_message.payload == {"status": "running"}


class TestWebSocketSinkRendering:
    def test_job_failed_renders_error_level_message(self, real_commit_test_db: Session):
        db = real_commit_test_db
        org, user, _ = create_test_organization_and_user(
            db, "WS Sink Org 5", "wssink5@events-test.com", "WS Sink User"
        )
        user.organization_id = org.id
        db.commit()
        job = _job_row(db, org, user, celery_task_id="ws-sink-task-5")

        event = JobFailed(
            **_base(
                organization_id=org.id,
                user_id=user.id,
                celery_task_id="ws-sink-task-5",
                error_type="ValueError",
                error_message="bad input",
            )
        )

        with patch(_PATCH_TARGET) as mock_publish:
            WebSocketSink().deliver(event, db=None)

        activity_call = mock_publish.call_args_list[0]
        activity_message, activity_target = activity_call.args
        assert activity_target.channel == f"job:{job.id}"
        assert activity_message.payload == {
            "level": "error",
            "message": "Job failed: ValueError: bad input",
        }

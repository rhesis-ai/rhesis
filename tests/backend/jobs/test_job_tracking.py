"""Job rows are recorded at dispatch and advanced by the lifecycle hooks.

The Jobs screen is only as good as this wiring: if ``launch_job`` does not
record a row, the work is invisible, and if the hooks do not advance it, every
job looks like it is still queued.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/jobs/test_job_tracking.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.models.enums import JobStatus
from rhesis.backend.app.models.job import Job
from rhesis.backend.jobs import tracking
from tests.backend.fixtures.test_setup import create_test_organization_and_user


class TestJobTypeDerivation:
    def test_strips_our_package_prefix(self):
        assert (
            tracking.job_type_for("rhesis.backend.jobs.embedding.generate_embedding")
            == "embedding.generate_embedding"
        )

    def test_leaves_foreign_names_alone(self):
        assert tracking.job_type_for("celery.chord_unlock") == "celery.chord_unlock"

    def test_high_frequency_types_are_untracked(self):
        """A row per trace or per request would bury the screen in noise."""
        assert not tracking.is_tracked("rhesis.backend.jobs.usage.accrue_usage")
        assert not tracking.is_tracked(
            "rhesis.backend.jobs.telemetry.evaluate.evaluate_turn_trace_metrics"
        )

    def test_user_visible_types_are_tracked(self):
        assert tracking.is_tracked("rhesis.backend.jobs.generate_and_save_test_set")
        assert tracking.is_tracked("rhesis.backend.jobs.execute_test_configuration")


class TestCreateJob:
    def test_records_a_queued_row(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Tracking Org", "track@tracking-test.com", "Track User"
        )
        celery_task_id = str(uuid.uuid4())

        job_id = tracking.create_job(
            test_db,
            celery_task_id=celery_task_id,
            task_name="rhesis.backend.jobs.generate_and_save_test_set",
            name="Generate and Save Test Set",
            organization_id=str(org.id),
            user_id=str(user.id),
        )

        assert job_id is not None
        job = test_db.query(Job).filter(Job.id == job_id).first()
        assert job.status == JobStatus.QUEUED.value
        assert job.job_type == "generate_and_save_test_set"
        assert job.name == "Generate and Save Test Set"
        assert job.celery_task_id == celery_task_id
        assert job.queued_at is not None
        assert job.started_at is None
        assert job.attempt == 0

    def test_untracked_type_records_nothing(self, test_db: Session):
        org, user, _ = create_test_organization_and_user(
            test_db, "Tracking Org Skip", "skip@tracking-test.com", "Skip User"
        )
        before = test_db.query(Job).count()

        job_id = tracking.create_job(
            test_db,
            celery_task_id=str(uuid.uuid4()),
            task_name="rhesis.backend.jobs.usage.accrue_usage",
            organization_id=str(org.id),
            user_id=str(user.id),
        )

        assert job_id is None
        assert test_db.query(Job).count() == before

    def test_failure_returns_none_rather_than_raising(self, test_db: Session):
        """Bookkeeping must not be able to break the work it describes."""
        # job_type is NOT NULL; passing a task_name of "" still yields a row,
        # so force a real failure by handing it a bad organization id.
        job_id = tracking.create_job(
            test_db,
            celery_task_id=str(uuid.uuid4()),
            task_name="rhesis.backend.jobs.generate_and_save_test_set",
            organization_id="not-a-uuid",
        )
        assert job_id is None
        test_db.rollback()


@pytest.mark.parametrize(
    "transition,expected_status,sets_finished",
    [
        ("mark_running", JobStatus.RUNNING, False),
        ("mark_completed", JobStatus.COMPLETED, True),
        ("mark_cancelled", JobStatus.CANCELLED, True),
    ],
)
def test_transitions_move_status(
    real_commit_test_db: Session, transition, expected_status, sets_finished
):
    """The mark_* helpers open their own session, so the row must really be committed."""
    org, user, _ = create_test_organization_and_user(
        real_commit_test_db,
        f"Transition Org {transition}",
        f"{transition}@tracking-test.com",
        "Transition User",
    )
    celery_task_id = str(uuid.uuid4())
    tracking.create_job(
        real_commit_test_db,
        celery_task_id=celery_task_id,
        task_name="rhesis.backend.jobs.generate_and_save_test_set",
        organization_id=str(org.id),
        user_id=str(user.id),
    )
    real_commit_test_db.commit()

    getattr(tracking, transition)(celery_task_id, str(org.id), str(user.id), "")

    real_commit_test_db.expire_all()
    job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
    assert job.status == expected_status.value
    if sets_finished:
        assert job.finished_at is not None


def test_mark_failed_records_the_error(real_commit_test_db: Session):
    org, user, _ = create_test_organization_and_user(
        real_commit_test_db, "Fail Org", "fail@tracking-test.com", "Fail User"
    )
    celery_task_id = str(uuid.uuid4())
    tracking.create_job(
        real_commit_test_db,
        celery_task_id=celery_task_id,
        task_name="rhesis.backend.jobs.generate_and_save_test_set",
        organization_id=str(org.id),
        user_id=str(user.id),
    )
    real_commit_test_db.commit()

    tracking.mark_failed(
        celery_task_id, str(org.id), str(user.id), "", error=ValueError("endpoint unreachable")
    )

    real_commit_test_db.expire_all()
    job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
    assert job.status == JobStatus.FAILED.value
    assert job.error_message == "endpoint unreachable"
    assert job.error_type == "ValueError"


def test_mark_retrying_keeps_the_job_running(real_commit_test_db: Session):
    """A retry is not terminal: showing it as failed would be a lie."""
    org, user, _ = create_test_organization_and_user(
        real_commit_test_db, "Retry Org", "retry@tracking-test.com", "Retry User"
    )
    celery_task_id = str(uuid.uuid4())
    tracking.create_job(
        real_commit_test_db,
        celery_task_id=celery_task_id,
        task_name="rhesis.backend.jobs.generate_and_save_test_set",
        organization_id=str(org.id),
        user_id=str(user.id),
    )
    real_commit_test_db.commit()
    tracking.mark_running(celery_task_id, str(org.id), str(user.id), "")

    tracking.mark_retrying(celery_task_id, str(org.id), str(user.id), "", attempt=2)

    real_commit_test_db.expire_all()
    job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
    assert job.status == JobStatus.RUNNING.value
    assert job.attempt == 2


def test_unknown_celery_id_is_a_no_op(real_commit_test_db: Session):
    """Jobs dispatched before this shipped have no row; that must not raise."""
    org, user, _ = create_test_organization_and_user(
        real_commit_test_db, "Noop Org", "noop@tracking-test.com", "Noop User"
    )
    tracking.mark_completed(str(uuid.uuid4()), str(org.id), str(user.id), "")


def test_set_progress_records_both_bounds(real_commit_test_db: Session):
    org, user, _ = create_test_organization_and_user(
        real_commit_test_db, "Progress Org", "progress@tracking-test.com", "Progress User"
    )
    celery_task_id = str(uuid.uuid4())
    tracking.create_job(
        real_commit_test_db,
        celery_task_id=celery_task_id,
        task_name="rhesis.backend.jobs.generate_and_save_test_set",
        organization_id=str(org.id),
        user_id=str(user.id),
    )
    real_commit_test_db.commit()

    tracking.set_progress(celery_task_id, str(org.id), str(user.id), "", current=40, total=120)

    real_commit_test_db.expire_all()
    job = real_commit_test_db.query(Job).filter(Job.celery_task_id == celery_task_id).first()
    assert (job.progress_current, job.progress_total) == (40, 120)

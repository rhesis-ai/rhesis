"""jobs/retention.py: the sweep is disabled by default, keys job deletion on
``finished_at`` (never on ``created_at`` alone, so a long-running job is
never swept), and loops per organization since both tables' tenant_isolation
RLS policy is FORCE'd. Integration-style, using ``real_commit_test_db``: the
sweep opens its own ``SessionLocal()`` connections, so writes have to be
genuinely committed for it to see them -- same reason the events tests use
this fixture rather than plain ``test_db``.

Helpers return plain ids, not ORM objects: a row this test expects to be
deleted would otherwise raise ``ObjectDeletedError`` the moment an
already-expired object's attribute (e.g. ``.id``) is read back after the
sweep runs.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.models.activity_log import ActivityLog
from rhesis.backend.app.models.job import Job
from rhesis.backend.jobs import retention
from rhesis.backend.jobs.retention import sweep_expired_jobs
from tests.backend.fixtures.test_setup import create_test_organization_and_user

_NOW = datetime.now(timezone.utc)
_OLD = _NOW - timedelta(days=100)
_RECENT = _NOW - timedelta(days=1)


def _settings(monkeypatch, *, enabled: bool, retention_days: int = 30):
    monkeypatch.setattr(
        "rhesis.backend.jobs.retention.get_job_retention_settings",
        lambda: SimpleNamespace(enabled=enabled, retention_days=retention_days),
    )


def _org(db: Session, name: str, email: str):
    org, user, _ = create_test_organization_and_user(db, name, email, f"{name} User")
    user.organization_id = org.id
    db.commit()
    return org, user


def _job(db: Session, org, user, *, finished_at, status="completed", deleted_at=None) -> str:
    job = Job(
        organization_id=org.id,
        user_id=user.id,
        job_type="test.job",
        status=status,
        finished_at=finished_at,
        deleted_at=deleted_at,
    )
    db.add(job)
    db.commit()
    job_id = str(job.id)
    db.expunge(job)
    return job_id


def _activity_log(db: Session, org, *, created_at, job_id=None) -> str:
    entry = ActivityLog(
        organization_id=org.id,
        job_id=job_id,
        level="info",
        message="test entry",
        created_at=created_at,
    )
    db.add(entry)
    db.commit()
    entry_id = str(entry.id)
    db.expunge(entry)
    return entry_id


def _job_exists(db: Session, job_id: str) -> bool:
    """Raw SQL, not db.query: a soft-deleted row is hidden from the ORM by the
    global soft-delete listener, which would make "still there" and "gone"
    indistinguishable in TestSweepIncludesSoftDeletedRows below.
    """
    db.expire_all()
    return (
        db.execute(text("SELECT 1 FROM job WHERE id = :id"), {"id": job_id}).first() is not None
    )


def _activity_log_exists(db: Session, entry_id: str) -> bool:
    db.expire_all()
    return (
        db.execute(text("SELECT 1 FROM activity_log WHERE id = :id"), {"id": entry_id}).first()
        is not None
    )


@pytest.mark.integration
class TestSweepDisabledByDefault:
    def test_disabled_deletes_nothing(self, monkeypatch, real_commit_test_db: Session):
        _settings(monkeypatch, enabled=False)
        db = real_commit_test_db
        org, user = _org(db, "Retention Disabled Org", "retention-disabled@events-test.com")
        old_job_id = _job(db, org, user, finished_at=_OLD)

        result = sweep_expired_jobs()

        assert result == {"enabled": False}
        assert _job_exists(db, old_job_id)


@pytest.mark.integration
class TestSweepDeletesPastTheWindow:
    def test_deletes_finished_jobs_past_cutoff_but_keeps_recent_and_running(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org, user = _org(db, "Retention Org", "retention@events-test.com")

        old_finished_id = _job(db, org, user, finished_at=_OLD)
        recent_finished_id = _job(db, org, user, finished_at=_RECENT)
        still_running_id = _job(db, org, user, finished_at=None, status="running")

        result = sweep_expired_jobs()

        assert result["enabled"] is True
        assert result["jobs_deleted"] >= 1
        assert not _job_exists(db, old_finished_id)
        assert _job_exists(db, recent_finished_id)
        assert _job_exists(db, still_running_id)

    def test_deletes_old_activity_log_rows_regardless_of_job(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org, _user = _org(db, "Retention Log Org", "retention-log@events-test.com")

        # Not tied to any job -- a standalone entry must still be swept on
        # its own created_at, per the module docstring.
        old_entry_id = _activity_log(db, org, created_at=_OLD)
        recent_entry_id = _activity_log(db, org, created_at=_RECENT)

        result = sweep_expired_jobs()

        assert result["activity_log_deleted"] >= 1
        assert not _activity_log_exists(db, old_entry_id)
        assert _activity_log_exists(db, recent_entry_id)

    def test_deleting_an_expired_job_cascades_its_activity_log(
        self, monkeypatch, real_commit_test_db: Session
    ):
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org, user = _org(db, "Retention Cascade Org", "retention-cascade@events-test.com")

        old_job_id = _job(db, org, user, finished_at=_OLD)
        # This entry's own created_at is recent, so the activity_log sweep
        # alone would keep it -- only the job-row cascade removes it.
        entry_id = _activity_log(db, org, created_at=_RECENT, job_id=old_job_id)

        sweep_expired_jobs()

        assert not _job_exists(db, old_job_id)
        assert not _activity_log_exists(db, entry_id)


@pytest.mark.integration
class TestSweepIncludesSoftDeletedRows:
    def test_soft_deleted_rows_past_the_window_are_hard_deleted(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """The whole reason job/activity_log are excluded from the recycle bin
        (see routers/recycle.py and the d2c3b4a5e6f7 migration docstring) is
        that this sweep hard-deletes them "so rows do not accumulate invisibly
        behind the soft-delete filter". A soft-deleted row the sweep skipped
        would be exactly that accumulation, and invisible to the ORM too.
        """
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org, user = _org(db, "Retention Soft Org", "retention-soft@events-test.com")

        soft_deleted_id = _job(db, org, user, finished_at=_OLD, deleted_at=_OLD)

        sweep_expired_jobs()

        assert not _job_exists(db, soft_deleted_id)


@pytest.mark.integration
class TestSweepCoversEveryOrganization:
    def test_sweeps_across_multiple_organizations(self, monkeypatch, real_commit_test_db: Session):
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org_a, user_a = _org(db, "Retention Multi Org A", "retention-a@events-test.com")
        org_b, user_b = _org(db, "Retention Multi Org B", "retention-b@events-test.com")

        job_a_id = _job(db, org_a, user_a, finished_at=_OLD)
        job_b_id = _job(db, org_b, user_b, finished_at=_OLD)

        sweep_expired_jobs()

        assert not _job_exists(db, job_a_id)
        assert not _job_exists(db, job_b_id)

    def test_sweeping_one_org_never_touches_another_orgs_rows(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """Regression: _sweep_organization originally scoped only via
        bind_scope_to_session and let the ORM auto-filter inject
        organization_id. That listener is before_compile and does not apply to
        Query.delete(), so sweeping one org deleted every org's expired rows.
        The delete now filters organization_id explicitly.
        """
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org_a, user_a = _org(db, "Retention Iso Org A", "retention-iso-a@events-test.com")
        org_b, user_b = _org(db, "Retention Iso Org B", "retention-iso-b@events-test.com")

        job_a_id = _job(db, org_a, user_a, finished_at=_OLD)
        job_b_id = _job(db, org_b, user_b, finished_at=_OLD)

        cutoff = _NOW - timedelta(days=30)
        retention._sweep_organization(str(org_b.id), cutoff)

        assert _job_exists(db, job_a_id), "sweeping org_b must not delete org_a's rows"
        assert not _job_exists(db, job_b_id)

    def test_one_organizations_failure_does_not_block_the_rest(
        self, monkeypatch, real_commit_test_db: Session
    ):
        """A per-org exception must not abort the loop -- the whole point of
        scoping by organization is that one org's data never gates
        another's retention."""
        _settings(monkeypatch, enabled=True, retention_days=30)
        db = real_commit_test_db
        org_a, user_a = _org(db, "Retention Fail Org A", "retention-fail-a@events-test.com")
        org_b, user_b = _org(db, "Retention Fail Org B", "retention-fail-b@events-test.com")

        job_a_id = _job(db, org_a, user_a, finished_at=_OLD)
        job_b_id = _job(db, org_b, user_b, finished_at=_OLD)

        real_sweep = retention._sweep_organization

        def flaky_sweep(organization_id, cutoff):
            if organization_id == str(org_a.id):
                raise RuntimeError("simulated failure")
            return real_sweep(organization_id, cutoff)

        monkeypatch.setattr(retention, "_sweep_organization", flaky_sweep)

        sweep_expired_jobs()

        # org_a's failure is swallowed (logged, not raised) rather than
        # aborting the loop, so org_a keeps its (would-be-expired) job...
        assert _job_exists(db, job_a_id)
        # ...while org_b is still swept normally.
        assert not _job_exists(db, job_b_id)

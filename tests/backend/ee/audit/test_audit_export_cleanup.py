"""Deleting audit export files a week after their job finished.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_export_cleanup.py -v
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import status

from rhesis.backend.app.models.job import Job
from rhesis.backend.app.services import audit_retention
from rhesis.backend.ee.audit import register_audit
from rhesis.backend.ee.audit.export import cleanup
from rhesis.backend.ee.audit.export import service as export_service
from rhesis.backend.ee.audit.router import FILE_GONE
from rhesis.backend.jobs import audit_retention as job
from tests.backend.ee.audit.test_audit_events_api import (
    T0,
    _audit_log_registered,  # noqa: F401  (autouse fixture)
    _auth,
    _ee,
    _member,
    _no_self_audit,  # noqa: F401  (autouse fixture)
)
from tests.backend.ee.audit.test_audit_export import EXPORTS, _finished_job, _local_storage
from tests.backend.fixtures.rls import as_org

pytestmark = [pytest.mark.ee, pytest.mark.integration]

# T0 is when every test job finished.
EXPIRED = T0 + cleanup.FILE_LIFETIME + timedelta(seconds=1)


@pytest.fixture
def storage(tmp_path):
    return _local_storage(tmp_path)


def _ids(db):
    # Plain ids: a loaded Organization reloads under whichever org is scoped, and RLS hides it.
    org, user, token = _member(db, "Admin")
    return SimpleNamespace(id=org.id), SimpleNamespace(id=user.id), token


@pytest.fixture
def admin(test_db):
    return _ids(test_db)


def _export(db, storage, org, user, *, write=True, **kwargs) -> Job:
    export_job = _finished_job(db, org.id, user.id, **kwargs)
    fmt = export_job.job_metadata["format"]
    if write:
        storage.put_object_chunks([b"{}\n"], _path(org.id, export_job, fmt))
    return export_job


def _path(org_id, export_job, fmt="jsonl") -> str:
    return export_service.storage_path(org_id, export_job.celery_task_id, fmt)


def _clean(db, org, now, storage) -> int:
    with as_org(db, org.id):
        return cleanup.delete_expired_exports(db, org, now, storage)


def _deleted_at(db, org_id, export_job):
    with as_org(db, org_id):
        db.refresh(export_job)
    return (export_job.job_metadata or {}).get(export_service.FILE_DELETED_KEY)


class TestDeleteExpiredExports:
    def test_keeps_a_file_for_its_lifetime(self, test_db, storage, admin):
        org, user, _ = admin
        export_job = _export(test_db, storage, org, user)

        assert _clean(test_db, org, T0 + cleanup.FILE_LIFETIME, storage) == 0
        assert storage.object_exists(_path(org.id, export_job))
        assert _deleted_at(test_db, org.id, export_job) is None

        assert _clean(test_db, org, EXPIRED, storage) == 1
        assert not storage.object_exists(_path(org.id, export_job))
        assert _deleted_at(test_db, org.id, export_job) == EXPIRED.isoformat()

    def test_failed_and_csv_exports_go_too(self, test_db, storage, admin):
        org, user, _ = admin
        failed = _export(test_db, storage, org, user, fmt="csv", job_status="failed")
        assert _clean(test_db, org, EXPIRED, storage) == 1
        assert not storage.object_exists(_path(org.id, failed, "csv"))

    def test_a_job_with_no_finish_time_counts_from_creation(self, test_db, storage, admin):
        org, user, _ = admin
        export_job = _export(test_db, storage, org, user, job_status="running")
        with as_org(test_db, org.id):
            export_job.finished_at = None
            export_job.created_at = T0
            test_db.flush()

        assert _clean(test_db, org, EXPIRED, storage) == 1
        assert not storage.object_exists(_path(org.id, export_job))

    def test_a_file_already_gone_is_marked_and_not_looked_at_again(self, test_db, storage, admin):
        org, user, _ = admin
        export_job = _export(test_db, storage, org, user, write=False)

        assert _clean(test_db, org, EXPIRED, storage) == 1
        assert _deleted_at(test_db, org.id, export_job) == EXPIRED.isoformat()
        with patch.object(storage, "remove_object") as remove:
            assert _clean(test_db, org, EXPIRED + timedelta(days=1), storage) == 0
        remove.assert_not_called()

    def test_a_storage_error_on_one_file_does_not_stop_the_rest(self, test_db, storage, admin):
        org, user, _ = admin
        broken, fine = (_export(test_db, storage, org, user) for _ in range(2))
        real_remove = storage.remove_object

        def remove(path):
            if path == _path(org.id, broken):
                raise OSError("storage down")
            return real_remove(path)

        with patch.object(storage, "remove_object", side_effect=remove):
            assert _clean(test_db, org, EXPIRED, storage) == 1

        assert not storage.object_exists(_path(org.id, fine))
        assert _deleted_at(test_db, org.id, fine) == EXPIRED.isoformat()
        # Left for the next run.
        assert storage.object_exists(_path(org.id, broken))
        assert _deleted_at(test_db, org.id, broken) is None

    def test_never_touches_another_orgs_files(self, test_db, storage, admin):
        org, user, _ = admin
        other, other_user, _ = _ids(test_db)
        mine = _export(test_db, storage, org, user)
        theirs = _export(test_db, storage, other, other_user)

        assert _clean(test_db, org, EXPIRED, storage) == 1

        assert not storage.object_exists(_path(org.id, mine))
        assert storage.object_exists(_path(other.id, theirs))
        assert _deleted_at(test_db, other.id, theirs) is None

    def test_other_job_types_are_left_alone(self, test_db, storage, admin):
        org, user, _ = admin
        other_job = _finished_job(test_db, org.id, user.id, job_type="test_set.count")
        assert _clean(test_db, org, EXPIRED, storage) == 0
        assert _deleted_at(test_db, org.id, other_job) is None


class TestDownloadAfterCleanup:
    def test_says_the_file_no_longer_exists(self, client, test_db, storage, admin):
        org, user, token = admin
        export_job = _export(test_db, storage, org, user)
        _clean(test_db, org, EXPIRED, storage)

        # Even on cloud storage, where the route would otherwise sign a link unchecked.
        with (
            _ee(),
            patch("rhesis.backend.ee.audit.router.StorageService", lambda: storage),
            patch.object(storage, "presigned_url", return_value="https://signed/x"),
        ):
            resp = client.get(f"{EXPORTS}/{export_job.id}/download", headers=_auth(token))

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"] == FILE_GONE


class TestPurgeJob:
    def test_register_audit_hooks_the_cleanup_into_the_purge(self):
        register_audit()
        assert audit_retention.export_cleanup() is cleanup.delete_expired_exports

    def test_cleans_an_org_on_its_own_session(
        self, real_commit_test_db, test_org_id, authenticated_user_id, storage
    ):
        """The real path: a fresh session, scoped by the job, under RLS, committing the marker."""
        db = real_commit_test_db
        org = SimpleNamespace(id=uuid.UUID(test_org_id))
        export_job = _export(db, storage, org, SimpleNamespace(id=authenticated_user_id))
        db.commit()
        try:
            register_audit()
            with patch.object(cleanup, "StorageService", lambda: storage):
                assert job._clean_exports(org, EXPIRED) == 1
            assert not storage.object_exists(_path(org.id, export_job))
            assert _deleted_at(db, org.id, export_job) == EXPIRED.isoformat()
        finally:
            with as_org(db, org.id):
                db.delete(export_job)
                db.commit()

    def test_a_failed_cleanup_does_not_fail_the_purge(self):
        orgs = [SimpleNamespace(id=uuid.uuid4()) for _ in range(2)]

        def clean(org, now):
            if org is orgs[0]:
                raise OSError("storage down")
            return 2

        with (
            patch.object(job, "_organizations", return_value=orgs),
            patch.object(job, "_purge_organization", return_value=1),
            patch.object(job, "_clean_exports", side_effect=clean),
        ):
            result = job.sweep_expired_audit_events()

        assert result == {
            "enabled": True,
            "events_purged": 2,
            "orgs_purged": 2,
            "orgs_failed": 0,
            "export_files_deleted": 2,
            "export_cleanups_failed": 1,
        }

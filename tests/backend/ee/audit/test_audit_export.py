"""Audit log export (``/audit-events/exports``) and the built-in Auditor role.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_export.py -v
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from sqlalchemy import text

from rhesis.backend.app.auth.capabilities import get_all_capabilities
from rhesis.backend.app.models.job import Job
from rhesis.backend.app.models.notification import Notification
from rhesis.backend.app.services.storage_service import StorageService
from rhesis.backend.ee.audit.export import jobs as export_jobs
from rhesis.backend.ee.audit.export import service as export_service
from rhesis.backend.ee.audit.schemas import AuditEventRead
from rhesis.backend.ee.rbac.models import ORG_WIDE_ACCESS_LEVEL, permissions_for_built_in_role
from tests.backend.ee.audit.test_audit_events_api import (
    T0,
    URL,
    _audit_log_registered,  # noqa: F401  (autouse fixture)
    _auth,
    _ee,
    _insert,
    _member,
    _no_self_audit,  # noqa: F401  (autouse fixture)
)
from tests.backend.ee.rbac._rbac_helpers import (
    _create_project,
    _ee_provider_active,
    _principal,
)
from tests.backend.fixtures.rls import as_org

pytestmark = [pytest.mark.ee, pytest.mark.integration]

EXPORTS = f"{URL}exports"


def _local_storage(tmp_path) -> StorageService:
    with patch.dict(
        os.environ,
        {"STORAGE_SERVICE_URI": f"file://{tmp_path}", "LOCAL_STORAGE_PATH": str(tmp_path)},
    ):
        return StorageService()


@contextmanager
def _dispatch():
    """Capture the job dispatch instead of publishing to a broker."""
    with patch.object(export_jobs.export_audit_log, "apply_async") as apply_async:
        apply_async.return_value = MagicMock(id="unused")
        yield apply_async


def _post(client, token, body: dict, licensed: bool = True):
    with _ee(audit_log_licensed=licensed), _dispatch() as apply_async:
        return client.post(EXPORTS, json=body, headers=_auth(token)), apply_async


def _exported_rows(db, org_id) -> list:
    with as_org(db, org_id):
        return db.execute(
            text(
                "SELECT actor_id, changes FROM audit_event "
                "WHERE organization_id = CAST(:org AS uuid) AND action = 'audit_log.exported'"
            ),
            {"org": str(org_id)},
        ).all()


@pytest.fixture
def admin(test_db):
    org, user, token = _member(test_db, "Admin")
    return org.id, user.id, token


# ---------------------------------------------------------------------------
# Starting an export
# ---------------------------------------------------------------------------


class TestStartExport:
    def test_queues_an_org_wide_job_and_records_the_export(self, client, test_db, admin):
        org_id, user_id, token = admin
        expr = "startswith(action,'endpoint.')"
        resp, apply_async = _post(client, token, {"format": "csv", "filter": expr})

        assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
        body = resp.json()
        kwargs = apply_async.call_args.kwargs
        assert kwargs["task_id"] == body["task_id"]
        assert kwargs["kwargs"]["export_format"] == "csv"
        assert kwargs["kwargs"]["odata_filter"] == expr
        assert kwargs["headers"]["organization_id"] == str(org_id)
        assert "project_id" not in kwargs["headers"]

        with as_org(test_db, org_id):
            job = test_db.query(Job).filter(Job.celery_task_id == body["task_id"]).one()
        assert str(job.id) == body["job_id"]
        assert job.job_type == export_service.JOB_TYPE
        assert job.project_id is None
        assert job.job_metadata["format"] == "csv"
        assert job.job_metadata["filter"] == expr

        (row,) = _exported_rows(test_db, org_id)
        assert row.actor_id == user_id
        assert {c["field"]: c["after"] for c in row.changes} == {
            "format": "csv",
            "filter": expr,
            "sort_order": "desc",
        }

    def test_a_bad_filter_is_refused_before_anything_runs(self, client, test_db, admin):
        org_id, _, token = admin
        resp, apply_async = _post(client, token, {"filter": "nope eq 'x'"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.text
        apply_async.assert_not_called()
        assert _exported_rows(test_db, org_id) == []

    def test_unknown_format(self, client, admin):
        _, _, token = admin
        resp, _ = _post(client, token, {"format": "xlsx"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("role", ["Viewer", "Member"])
    def test_roles_without_export_are_denied(self, client, test_db, role):
        _, _, token = _member(test_db, role)
        resp, apply_async = _post(client, token, {})
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        apply_async.assert_not_called()

    def test_auditor_can_export(self, client, test_db):
        _, _, token = _member(test_db, "Auditor")
        resp, _ = _post(client, token, {})
        assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text

    def test_not_found_without_the_audit_log(self, client, admin):
        _, _, token = admin
        resp, apply_async = _post(client, token, {}, licensed=False)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        apply_async.assert_not_called()


# ---------------------------------------------------------------------------
# Writing the file
# ---------------------------------------------------------------------------


@pytest.fixture
def rows(test_db, admin):
    """Five events a day apart; the last has content stored and a formula for a name."""
    org_id, _, _ = admin
    ids = [
        _insert(test_db, org_id, action, T0 + timedelta(days=i))
        for i, action in enumerate(
            ["endpoint.created", "endpoint.updated", "metric.updated", "endpoint.deleted"]
        )
    ]
    with as_org(test_db, org_id):
        ids.append(
            test_db.execute(
                text(
                    "INSERT INTO audit_event (organization_id, occurred_at, action, outcome, "
                    "actor_type, actor_label, channel, trace_id, span_id, changes, "
                    "content_changes) VALUES (CAST(:org AS uuid), :at, 'test_set.created', "
                    "'success', 'user', :label, 'web', 't1', 's1', "
                    'CAST(\'[{"field": "name", "kind": "value"}]\' AS jsonb), '
                    "'secret prompt') RETURNING id"
                ),
                {"org": str(org_id), "at": T0 + timedelta(days=4), "label": '=HYPERLINK("x")'},
            ).scalar_one()
        )
    return org_id, ids


def _run(test_db, tmp_path, org_id, fmt="jsonl", until=None, **kwargs):
    storage = _local_storage(tmp_path)
    path = export_service.storage_path(org_id, uuid.uuid4(), fmt)
    progress = MagicMock()
    with as_org(test_db, org_id):
        result = export_service.run_export(
            test_db,
            storage,
            str(org_id),
            fmt=fmt,
            filter=kwargs.get("filter"),
            sort_order=kwargs.get("sort_order", "desc"),
            until=until or datetime.now(timezone.utc),
            path=path,
            progress=progress,
        )
    data = b"".join(storage.iter_object(path)).decode()
    return result, data, progress


class TestRunExport:
    def test_jsonl_has_the_list_shape_and_never_content(self, test_db, tmp_path, rows):
        org_id, ids = rows
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=True):
            result, data, _ = _run(test_db, tmp_path, org_id)

        lines = [json.loads(line) for line in data.splitlines()]
        assert [line["id"] for line in lines] == [str(i) for i in reversed(ids)]
        assert set(lines[0]) == set(AuditEventRead.model_fields)
        assert "secret prompt" not in data
        assert result["rows"] == 5

    def test_filter_order_and_until(self, test_db, tmp_path, rows):
        org_id, ids = rows
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=True):
            _, data, _ = _run(
                test_db,
                tmp_path,
                org_id,
                filter="startswith(action,'endpoint.')",
                sort_order="asc",
                until=T0 + timedelta(days=2),
            )
        assert [json.loads(line)["id"] for line in data.splitlines()] == [
            str(ids[0]),
            str(ids[1]),
        ]

    @pytest.mark.parametrize("sort_order", ["asc", "desc"])
    def test_batches_walk_every_row_once(self, test_db, tmp_path, rows, sort_order, monkeypatch):
        org_id, ids = rows
        monkeypatch.setattr(export_service, "BATCH_SIZE", 2)
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=True):
            _, data, progress = _run(test_db, tmp_path, org_id, sort_order=sort_order)
        got = [json.loads(line)["id"] for line in data.splitlines()]
        expected = [str(i) for i in ids]
        assert got == (expected if sort_order == "asc" else expected[::-1])
        assert progress.call_args_list[0].args == (0, 5)
        assert progress.call_args_list[-1].args == (5, 5)

    def test_csv(self, test_db, tmp_path, rows):
        org_id, _ = rows
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=True):
            _, data, _ = _run(test_db, tmp_path, org_id, fmt="csv")
        table = list(csv.DictReader(io.StringIO(data)))
        assert list(table[0]) == export_service.CSV_COLUMNS
        assert len(table) == 5
        assert table[0]["actor_label"] == '\'=HYPERLINK("x")'
        assert json.loads(table[0]["changes"]) == [{"field": "name", "kind": "value"}]
        assert table[0]["project_id"] == ""

    def test_empty_export_is_an_empty_file(self, test_db, tmp_path, admin):
        org_id, _, _ = admin
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=True):
            result, data, _ = _run(test_db, tmp_path, org_id)
        assert (result["rows"], data) == (0, "")

    def test_refused_when_the_org_has_no_audit_log(self, test_db, tmp_path, admin):
        org_id, _, _ = admin
        with patch("rhesis.backend.ee.audit.export.service.audit_enabled", return_value=False):
            with pytest.raises(export_service.ExportNotAvailable):
                _run(test_db, tmp_path, org_id)

    def test_a_failed_write_leaves_no_file(self, tmp_path):
        storage = _local_storage(tmp_path)

        def chunks():
            yield b"first\n"
            raise OSError("bucket gone")

        with pytest.raises(OSError):
            storage.put_object_chunks(chunks(), "audit-exports/x.jsonl")
        assert not storage.object_exists("audit-exports/x.jsonl")


@pytest.mark.parametrize(
    "value, cell",
    [
        (None, ""),
        (403, "403"),
        ([{"a": 1}], '[{"a":1}]'),
        ("=1+1", "'=1+1"),
        ("+x", "'+x"),
        ("-x", "'-x"),
        ("@x", "'@x"),
        ("plain", "plain"),
    ],
)
def test_csv_cell(value, cell):
    assert export_service.csv_cell(value) == cell


# ---------------------------------------------------------------------------
# The Celery job, run eagerly against the test session
# ---------------------------------------------------------------------------


class TestExportJob:
    @pytest.fixture
    def job_env(self, test_db, tmp_path, monkeypatch):
        @contextmanager
        def _session(*_args, **_kwargs):
            yield test_db

        monkeypatch.setattr("rhesis.backend.jobs.base.get_db_with_tenant_variables", _session)
        storage = _local_storage(tmp_path)
        monkeypatch.setattr(export_jobs, "StorageService", lambda: storage)
        return storage

    def _apply(self, org_id, user_id, task_id, job_id):
        return export_jobs.export_audit_log.apply(
            kwargs={
                "export_format": "jsonl",
                "odata_filter": None,
                "sort_order": "desc",
                "until": datetime.now(timezone.utc).isoformat(),
            },
            task_id=task_id,
            headers={
                "organization_id": str(org_id),
                "user_id": str(user_id),
                "job_id": str(job_id),
            },
        )

    def _notification(self, test_db, org_id, user_id):
        with as_org(test_db, org_id):
            return (
                test_db.query(Notification)
                .filter(Notification.user_id == user_id)
                .filter(Notification.event_type == "audit_log.export_completed")
                .one()
            )

    def test_writes_the_file_and_notifies_with_the_download_link(
        self, test_db, job_env, rows, admin
    ):
        org_id, ids = rows
        _, user_id, _ = admin
        task_id, job_id = str(uuid.uuid4()), uuid.uuid4()
        with _ee():
            result = self._apply(org_id, user_id, task_id, job_id)

        assert result.successful(), result.traceback
        retval = result.get()
        assert retval["rows"] == 5
        assert retval["download_path"] == f"/audit-events/exports/{job_id}/download"
        assert not any("http" in str(v) for v in retval.values())
        data = b"".join(job_env.iter_object(export_service.storage_path(org_id, task_id, "jsonl")))
        assert len(data.splitlines()) == len(ids)

        note = self._notification(test_db, org_id, user_id)
        assert note.section == "jobs"
        assert not note.is_failure
        assert note.payload["job_id"] == str(job_id)
        assert note.payload["download_path"] == retval["download_path"]

    def test_a_lapsed_licence_fails_without_retrying(self, test_db, job_env, admin):
        org_id, user_id, _ = admin
        with _ee(audit_log_licensed=False):
            result = self._apply(org_id, user_id, str(uuid.uuid4()), uuid.uuid4())
        assert result.failed()
        assert isinstance(result.result, export_service.ExportNotAvailable)
        note = self._notification(test_db, org_id, user_id)
        assert note.is_failure
        assert "download_path" not in note.payload


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------


def _finished_job(db, org_id, user_id, *, fmt="jsonl", job_status="completed", job_type=None):
    with as_org(db, org_id):
        job = Job(
            celery_task_id=str(uuid.uuid4()),
            job_type=job_type or export_service.JOB_TYPE,
            status=job_status,
            job_metadata={"format": fmt},
            finished_at=T0,
            organization_id=org_id,
            user_id=user_id,
        )
        db.add(job)
        db.flush()
    return job


class TestDownload:
    @pytest.fixture
    def storage(self, tmp_path):
        storage = _local_storage(tmp_path)
        with patch("rhesis.backend.ee.audit.router.StorageService", lambda: storage):
            yield storage

    def _write(self, storage, org_id, job, content=b'{"id":"1"}\n'):
        path = export_service.storage_path(org_id, job.celery_task_id, "jsonl")
        storage.put_object_chunks([content], path)

    def _get(self, client, token, job_id, licensed=True):
        with _ee(audit_log_licensed=licensed):
            return client.get(
                f"{EXPORTS}/{job_id}/download", headers=_auth(token), follow_redirects=False
            )

    def test_streams_the_file_and_records_a_read(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id)
        self._write(storage, org_id, job)
        with patch.object(export_service, "record_audit_event") as record:
            resp = self._get(client, token, job.id)
        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.content == b'{"id":"1"}\n'
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        assert 'filename="audit-log-20261001-120000.jsonl"' in resp.headers["content-disposition"]
        # Every download is recorded, with the job it came from.
        record.assert_called_once()
        assert record.call_args.args == (export_service.VIEWED, str(org_id))
        assert str(record.call_args.kwargs["resource_id"]) == str(job.id)

    def test_cloud_storage_redirects_to_a_short_link(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id)
        with patch.object(storage, "presigned_url", return_value="https://signed/x") as sign:
            resp = self._get(client, token, job.id)
        assert resp.status_code == status.HTTP_302_FOUND
        assert resp.headers["location"] == "https://signed/x"
        assert sign.call_args.kwargs["expires_in"] == export_service.LINK_SECONDS

    def test_not_ready(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id, job_status="running")
        assert self._get(client, token, job.id).status_code == status.HTTP_409_CONFLICT

    def test_another_job_type_is_not_an_export(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id, job_type="test_set.count")
        assert self._get(client, token, job.id).status_code == status.HTTP_404_NOT_FOUND

    def test_missing_file(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id)
        assert self._get(client, token, job.id).status_code == status.HTTP_404_NOT_FOUND

    def test_another_orgs_export_is_not_found(self, client, test_db, admin, storage):
        org_id, user_id, _ = admin
        job = _finished_job(test_db, org_id, user_id)
        self._write(storage, org_id, job)
        job_id = job.id
        _, _, other_token = _member(test_db, "Admin")
        assert self._get(client, other_token, job_id).status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("role, code", [("Auditor", 200), ("Viewer", 403), ("Member", 403)])
    def test_needs_audit_log_export(self, client, test_db, storage, role, code):
        org, user, token = _member(test_db, role)
        job = _finished_job(test_db, org.id, user.id)
        self._write(storage, org.id, job)
        assert self._get(client, token, job.id).status_code == code

    def test_not_found_without_the_audit_log(self, client, test_db, admin, storage):
        org_id, user_id, token = admin
        job = _finished_job(test_db, org_id, user_id)
        self._write(storage, org_id, job)
        assert (
            self._get(client, token, job.id, licensed=False).status_code
            == status.HTTP_404_NOT_FOUND
        )


# ---------------------------------------------------------------------------
# The Auditor role
# ---------------------------------------------------------------------------


class TestAuditorRole:
    def test_reads_everything_and_writes_nothing(self):
        caps = get_all_capabilities()
        auditor = permissions_for_built_in_role("Auditor", caps)
        reads = {c for c in caps if c.endswith(":read")}
        assert reads <= auditor
        assert {"audit_log:read", "audit_log:export", "recycle:view"} <= auditor
        # Beyond reads: export, the recycle bin view, and their own API tokens.
        own_tokens = {"token:create", "token:update", "token:delete"}
        assert auditor - reads == {"audit_log:export", "recycle:view", *own_tokens}
        assert "audit_log:manage" not in auditor

    def test_nests_between_viewer_and_admin(self):
        caps = get_all_capabilities()
        viewer = permissions_for_built_in_role("Viewer", caps)
        auditor = permissions_for_built_in_role("Auditor", caps)
        admin = permissions_for_built_in_role("Admin", caps)
        assert viewer <= auditor <= admin

    def test_sees_every_project_but_cannot_change_one(self, test_db):
        org, user, _ = _member(test_db, "Auditor")
        project_id = _create_project(test_db, org.id)
        principal = _principal(user.id, org.id)
        from rhesis.backend.app.auth.rbac import authorize

        with _ee_provider_active():
            assert authorize(principal, "test_set:read", project_id=project_id, db=test_db)
            assert not authorize(principal, "test_set:create", project_id=project_id, db=test_db)
        assert ORG_WIDE_ACCESS_LEVEL == 70

    def test_reads_settings_but_cannot_change_them(self, client, test_db):
        _, _, token = _member(test_db, "Auditor")
        with _ee():
            assert client.get(f"{URL}settings", headers=_auth(token)).status_code == 200
            resp = client.patch(f"{URL}settings", json={"mask_ip": False}, headers=_auth(token))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_viewer_cannot_read_settings(self, client, test_db):
        _, _, token = _member(test_db, "Viewer")
        with _ee():
            resp = client.get(f"{URL}settings", headers=_auth(token))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

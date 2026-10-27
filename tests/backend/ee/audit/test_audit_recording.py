"""Audit recording: changes on a session become ``audit_event`` rows in the same transaction."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from rhesis.backend.app import models
from rhesis.backend.app.crud.metric import add_metric_to_test_set
from rhesis.backend.app.crud.test_set import add_tests_to_test_set, remove_tests_from_test_set
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.models.audit_capture import SUMMARY_ID_LIMIT
from rhesis.backend.app.provenance import (
    ActorType,
    Channel,
    RequestProvenance,
    bind_job_provenance,
    bind_task_provenance,
    job_provenance,
    provenance_of,
    reset_task_provenance,
)
from rhesis.backend.app.utils.crud_utils import bulk_delete_by_ids
from rhesis.backend.ee.rbac.crud import replace_role_permissions
from rhesis.backend.ee.rbac.models import Permission, Role

_PROVENANCE_KEY = "_provenance"
# Rows other tests committed for real stay (the table is append-only), so each
# test reads only rows carrying its own request id.
_REQUEST_KEY = "_audit_test_request"


def _as_person(db, user_id: str) -> None:
    db.info[_PROVENANCE_KEY] = RequestProvenance(
        actor_type=ActorType.USER,
        actor_id=user_id,
        credential_id=None,
        credential_hint=None,
        channel=Channel.WEB,
        ip="203.0.113.7",
        user_agent="pytest",
        request_id=db.info[_REQUEST_KEY],
    )


def _as_job(db, user_id: str, job_id: uuid.UUID) -> None:
    bind_job_provenance(db, user_id=user_id, job_id=str(job_id), request_id=db.info[_REQUEST_KEY])


def _rows(db, org_id: str) -> list:
    return list(
        db.execute(
            text(
                "SELECT action, actor_type, actor_id, actor_label, channel, ip, resource_id, "
                "resource_label, job_id, changes FROM audit_event "
                "WHERE organization_id = CAST(:org AS uuid) AND request_id = :request "
                "ORDER BY recorded_at, id"
            ),
            {"org": org_id, "request": db.info[_REQUEST_KEY]},
        ).mappings()
    )


def _test_set(db, org_id, user_id, name="Audit set") -> models.TestSet:
    test_set = models.TestSet(name=name, organization_id=org_id, user_id=user_id)
    db.add(test_set)
    db.flush()
    return test_set


def _tests(db, org_id, user_id, count: int) -> list:
    tests = [models.Test(organization_id=org_id, user_id=user_id) for _ in range(count)]
    db.add_all(tests)
    db.flush()
    return tests


@pytest.fixture
def audit_db(test_db, test_org_id):
    """``test_db`` with a request id of its own to find this test's rows by."""
    assert FeatureRegistry.is_registered(FeatureName.AUDIT_LOG)
    test_db.info[_REQUEST_KEY] = f"req-{uuid.uuid4().hex}"
    assert _rows(test_db, test_org_id) == []
    return test_db


class TestChangesByAPerson:
    def test_create_records_actor_resource_and_values(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        _as_person(audit_db, authenticated_user_id)
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id)

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "test_set.created"
        assert row["actor_type"] == "user"
        assert str(row["actor_id"]) == authenticated_user_id
        assert row["actor_label"]
        assert row["channel"] == "web"
        assert str(row["ip"]) == "203.0.113.0"  # mask IP is on by default
        assert row["resource_id"] == test_set.id
        assert row["resource_label"] == "Audit set"
        assert {"field": "name", "kind": "value", "before": None, "after": "Audit set"} in (
            row["changes"]
        )

    def test_update_records_before_and_after(self, audit_db, test_org_id, authenticated_user_id):
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id, name="Old")
        _as_person(audit_db, authenticated_user_id)

        test_set.name = "New"
        audit_db.flush()

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "test_set.updated"
        assert row["resource_label"] == "New"
        assert row["changes"] == [
            {"field": "name", "kind": "value", "before": "Old", "after": "New"}
        ]

    def test_deleting_three_tests_writes_three_rows(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        ids = [t.id for t in _tests(audit_db, test_org_id, authenticated_user_id, 3)]
        _as_person(audit_db, authenticated_user_id)

        bulk_delete_by_ids(audit_db, models.Test, ids, organization_id=test_org_id)

        rows = _rows(audit_db, test_org_id)
        assert [r["action"] for r in rows] == ["test.deleted"] * 3
        assert {r["resource_id"] for r in rows} == set(ids)

    def test_secret_and_content_values_are_not_stored(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        _as_person(audit_db, authenticated_user_id)
        audit_db.add(
            models.Prompt(
                content="secret prompt", organization_id=test_org_id, user_id=authenticated_user_id
            )
        )
        audit_db.flush()

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "prompt.created"
        assert {"field": "content", "kind": "content"} in row["changes"]
        assert "secret prompt" not in str(row["changes"])

    def test_token_last_used_at_writes_nothing(self, audit_db, test_org_id, authenticated_user_id):
        token = audit_db.scalars(
            select(models.Token).where(models.Token.organization_id == test_org_id).limit(1)
        ).first()
        if token is None:
            pytest.skip("no token in the test org")
        _as_person(audit_db, authenticated_user_id)

        token.last_used_at = datetime.now(timezone.utc)
        audit_db.flush()

        assert _rows(audit_db, test_org_id) == []


class TestLinkTables:
    def test_link_changes_are_recorded_on_the_owner(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id)
        test_ids = [t.id for t in _tests(audit_db, test_org_id, authenticated_user_id, 2)]
        _as_person(audit_db, authenticated_user_id)

        add_tests_to_test_set(audit_db, test_set.id, test_ids, test_org_id, authenticated_user_id)
        remove_tests_from_test_set(audit_db, test_set.id, test_ids[:1], test_org_id)

        added, removed = _rows(audit_db, test_org_id)
        assert added["action"] == removed["action"] == "test_set.updated"
        assert added["resource_id"] == removed["resource_id"] == test_set.id
        assert added["resource_label"] == "Audit set"
        assert added["changes"] == [
            {"field": "tests", "kind": "value", "before": None, "after": sorted(map(str, test_ids))}
        ]
        assert removed["changes"] == [
            {"field": "tests", "kind": "value", "before": [str(test_ids[0])], "after": None}
        ]

    def test_link_insert_without_returning_is_recorded(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id)
        metric = models.Metric(
            name="Audit metric",
            evaluation_prompt="Is it right?",
            score_type="binary",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        audit_db.add(metric)
        audit_db.flush()
        _as_person(audit_db, authenticated_user_id)

        assert add_metric_to_test_set(
            audit_db, test_set.id, metric.id, authenticated_user_id, test_org_id
        )

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "test_set.updated"
        assert row["changes"][0]["field"] == "metrics"
        assert row["changes"][0]["after"] == [str(metric.id)]

    def test_role_permissions_are_recorded_on_the_role(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        permission_ids = list(audit_db.scalars(select(Permission.id).limit(2)))
        if len(permission_ids) < 2:
            pytest.skip("permission catalog not seeded")
        role = Role(name=f"audit-{uuid.uuid4().hex[:8]}", organization_id=test_org_id, level=10)
        audit_db.add(role)
        audit_db.flush()
        replace_role_permissions(audit_db, role.id, permission_ids[:1])
        audit_db.flush()
        _as_person(audit_db, authenticated_user_id)

        replace_role_permissions(audit_db, role.id, permission_ids[1:])
        audit_db.flush()

        # The bulk delete and the flushed inserts are separate writes, so two rows.
        removed, added = _rows(audit_db, test_org_id)
        assert removed["action"] == added["action"] == "role.updated"
        assert removed["resource_id"] == added["resource_id"] == role.id
        assert removed["changes"] == [
            {
                "field": "permissions",
                "kind": "value",
                "before": [str(permission_ids[0])],
                "after": None,
            }
        ]
        assert added["changes"] == [
            {
                "field": "permissions",
                "kind": "value",
                "before": None,
                "after": [str(permission_ids[1])],
            }
        ]


class TestJobs:
    def test_job_change_records_channel_and_originating_user(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id, name="Before")
        job_id = uuid.uuid4()
        _as_job(audit_db, authenticated_user_id, job_id)

        test_set.name = "After"
        audit_db.flush()

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "test_set.updated"
        assert row["channel"] == "job"
        assert row["actor_type"] == "system"
        assert str(row["actor_id"]) == authenticated_user_id
        assert row["job_id"] == job_id

    def test_job_creating_500_tests_writes_one_summary_row(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        job_id = uuid.uuid4()
        _as_job(audit_db, authenticated_user_id, job_id)

        ids = [t.id for t in _tests(audit_db, test_org_id, authenticated_user_id, 300)]
        ids += [t.id for t in _tests(audit_db, test_org_id, authenticated_user_id, 200)]
        assert _rows(audit_db, test_org_id) == []  # summarized at commit
        audit_db.commit()

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "test.created"
        assert row["job_id"] == job_id
        assert row["changes"]["count"] == 500
        assert sorted(row["changes"]["ids"]) == sorted(map(str, ids))
        assert 500 <= SUMMARY_ID_LIMIT

    def test_celery_task_provenance_covers_sessions_the_task_opens(
        self, audit_db, authenticated_user_id
    ):
        token = bind_task_provenance(
            job_provenance(user_id=authenticated_user_id, job_id=None, request_id=None)
        )
        try:
            provenance = provenance_of(audit_db)
        finally:
            reset_task_provenance(token)
        assert provenance.channel == Channel.JOB
        assert provenance.actor_id == authenticated_user_id
        assert provenance_of(audit_db) is None


class TestTransactionality:
    def test_rolled_back_change_leaves_no_row(self, audit_db, test_org_id, authenticated_user_id):
        _as_person(audit_db, authenticated_user_id)
        _test_set(audit_db, test_org_id, authenticated_user_id)
        assert len(_rows(audit_db, test_org_id)) == 1

        audit_db.rollback()

        assert _rows(audit_db, test_org_id) == []

    def test_audit_write_failure_fails_the_change(
        self, audit_db, test_org_id, authenticated_user_id, monkeypatch
    ):
        from rhesis.backend.ee.audit import sink

        def broken(*args, **kwargs):
            raise RuntimeError("audit store down")

        monkeypatch.setattr(sink, "insert_audit_event", broken)
        _as_person(audit_db, authenticated_user_id)

        audit_db.add(
            models.TestSet(name="Lost", organization_id=test_org_id, user_id=authenticated_user_id)
        )
        with pytest.raises(RuntimeError, match="audit store down"):
            audit_db.flush()
        audit_db.rollback()

        assert (
            audit_db.scalars(select(models.TestSet).where(models.TestSet.name == "Lost")).first()
            is None
        )


class TestNothingRecorded:
    def test_org_without_the_feature_writes_nothing(
        self, audit_db, test_org_id, authenticated_user_id, monkeypatch
    ):
        original = FeatureRegistry.is_available

        def no_audit(name, org):
            return False if name == FeatureName.AUDIT_LOG else original(name, org)

        monkeypatch.setattr(FeatureRegistry, "is_available", staticmethod(no_audit))
        _as_person(audit_db, authenticated_user_id)

        _test_set(audit_db, test_org_id, authenticated_user_id)

        assert _rows(audit_db, test_org_id) == []

    def test_session_without_provenance_writes_nothing(
        self, audit_db, test_org_id, authenticated_user_id
    ):
        test_set = _test_set(audit_db, test_org_id, authenticated_user_id)
        recorded = audit_db.execute(
            text("SELECT count(*) FROM audit_event WHERE resource_id = :id"), {"id": test_set.id}
        ).scalar()
        assert recorded == 0


class TestWithoutACallerSession:
    """Denials and failed sign-ins (5c) have no transaction to join."""

    @staticmethod
    def _denied(org_id: str, user_id: str, request_id: str):
        from rhesis.backend.events.types import AuditRecorded

        return AuditRecorded(
            occurred_at=datetime.now(timezone.utc),
            organization_id=org_id,
            user_id=user_id,
            trace_id="a" * 32,
            span_id="b" * 16,
            source="audit",
            action="endpoint.updated",
            outcome="denied",
            status_code=403,
            actor_type=ActorType.USER,
            channel=Channel.WEB,
            request_id=request_id,
        )

    def test_writes_on_its_own_session(self, audit_db, test_org_id, authenticated_user_id):
        from rhesis.backend.ee.audit.sink import AuditSink

        request_id = audit_db.info[_REQUEST_KEY]
        AuditSink().deliver(self._denied(test_org_id, authenticated_user_id, request_id), None)

        (row,) = _rows(audit_db, test_org_id)
        assert row["action"] == "endpoint.updated"

    def test_a_failure_is_logged_not_raised(
        self, audit_db, test_org_id, authenticated_user_id, monkeypatch, caplog
    ):
        from rhesis.backend.ee.audit import sink

        def broken(*args, **kwargs):
            raise RuntimeError("audit store down")

        monkeypatch.setattr(sink, "insert_audit_event", broken)
        request_id = audit_db.info[_REQUEST_KEY]

        sink.AuditSink().deliver(self._denied(test_org_id, authenticated_user_id, request_id), None)

        assert "Audit write failed" in caplog.text

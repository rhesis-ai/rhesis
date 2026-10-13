"""Audit log retention: the daily purge and deleted orgs.

``recorded_at`` is always the insert time, so tests cannot backdate a row.
Instead they move ``now`` forward: a row is expired when it was recorded
before ``now - retention``.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/audit/test_audit_retention.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from rhesis.backend.app import models
from rhesis.backend.app.crud.organization import delete_organization, merge_organization_settings
from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.services.audit_retention import (
    purge_expired_audit_events,
    retention_days,
)
from rhesis.backend.jobs import audit_retention as job
from tests.backend.ee.audit.test_audit_events_api import (
    T0,
    _audit_log_registered,  # noqa: F401  (autouse fixture)
    _ee,
    _insert,
    _member,
)
from tests.backend.ee.audit.test_audit_settings import _plan_retention
from tests.backend.fixtures.rls import as_org

pytestmark = [pytest.mark.ee, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _unlimited_plan():
    with _plan_retention(None):
        yield


def _clock(db) -> datetime:
    return db.execute(text("SELECT clock_timestamp()")).scalar_one()


def _org(db, org_id) -> models.Organization:
    with without_soft_delete_filter():
        return db.get(models.Organization, org_id)


def _purge(db, org_id, now: datetime, licensed: bool = True):
    with _ee(audit_log_licensed=licensed), as_org(db, org_id):
        return purge_expired_audit_events(db, _org(db, org_id), now)


def _actions(db, org_id) -> list[str]:
    with as_org(db, org_id):
        return list(
            db.execute(
                text(
                    "SELECT action FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                    "ORDER BY recorded_at, id"
                ),
                {"org": str(org_id)},
            ).scalars()
        )


def _purged_changes(db, org_id) -> list[dict]:
    with as_org(db, org_id):
        return list(
            db.execute(
                text(
                    "SELECT changes FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                    "AND action = 'audit_log.purged'"
                ),
                {"org": str(org_id)},
            ).scalars()
        )


@pytest.fixture
def org_with_old_and_new_row(test_db):
    """An org with one row recorded before ``boundary`` and one after."""
    org, _, _ = _member(test_db, "Admin")
    _insert(test_db, org.id, "endpoint.created", T0)
    boundary = _clock(test_db)
    _insert(test_db, org.id, "endpoint.updated", T0)
    return org.id, boundary


def _set_retention(db, org_id, days: int) -> None:
    merge_organization_settings(db, _org(db, org_id), {"audit_log": {"retention_days": days}})
    db.flush()


class TestPurge:
    def test_only_expired_rows_go_and_one_purged_row_records_it(
        self, test_db, org_with_old_and_new_row
    ):
        org_id, boundary = org_with_old_and_new_row

        assert _purge(test_db, org_id, boundary + timedelta(days=365)) == 1

        assert _actions(test_db, org_id) == ["endpoint.updated", "audit_log.purged"]
        (changes,) = _purged_changes(test_db, org_id)
        assert changes["count"] == 1
        assert datetime.fromisoformat(changes["before"]) == boundary

    def test_nothing_expired_purges_and_records_nothing(self, test_db, org_with_old_and_new_row):
        org_id, boundary = org_with_old_and_new_row

        assert _purge(test_db, org_id, boundary + timedelta(days=364)) == 0
        assert _actions(test_db, org_id) == ["endpoint.created", "endpoint.updated"]

    def test_running_twice_purges_once(self, test_db, org_with_old_and_new_row):
        org_id, boundary = org_with_old_and_new_row
        now = boundary + timedelta(days=365)

        assert _purge(test_db, org_id, now) == 1
        assert _purge(test_db, org_id, now) == 0
        assert len(_purged_changes(test_db, org_id)) == 1

    def test_uses_the_orgs_retention(self, test_db, org_with_old_and_new_row):
        org_id, boundary = org_with_old_and_new_row
        _set_retention(test_db, org_id, 90)

        assert _purge(test_db, org_id, boundary + timedelta(days=89)) == 0
        assert _purge(test_db, org_id, boundary + timedelta(days=90)) == 1

    def test_the_plan_caps_the_orgs_retention(self, test_db, org_with_old_and_new_row):
        org_id, boundary = org_with_old_and_new_row
        _set_retention(test_db, org_id, 1095)

        with _plan_retention(100):
            assert _purge(test_db, org_id, boundary + timedelta(days=100)) == 1

    def test_an_org_that_lost_the_feature_is_purged_on_its_choice(
        self, test_db, org_with_old_and_new_row
    ):
        org_id, boundary = org_with_old_and_new_row
        _set_retention(test_db, org_id, 1095)

        # No licence, so no plan cap: the stored 1095 days apply, not the plan's 100.
        with _plan_retention(100):
            assert _purge(test_db, org_id, boundary + timedelta(days=1094), licensed=False) == 0
            assert _purge(test_db, org_id, boundary + timedelta(days=1095), licensed=False) == 1

    def test_an_org_that_lost_the_feature_defaults_to_a_year(
        self, test_db, org_with_old_and_new_row
    ):
        org_id, boundary = org_with_old_and_new_row

        assert _purge(test_db, org_id, boundary + timedelta(days=364), licensed=False) == 0
        assert _purge(test_db, org_id, boundary + timedelta(days=365), licensed=False) == 1

    def test_other_orgs_rows_stay(self, test_db, org_with_old_and_new_row):
        org_id, boundary = org_with_old_and_new_row
        other, _, _ = _member(test_db, "Admin")
        _insert(test_db, other.id, "endpoint.created", T0)

        _purge(test_db, org_id, boundary + timedelta(days=365))
        assert _actions(test_db, other.id) == ["endpoint.created"]


class TestDeletedOrg:
    def test_deletion_freezes_the_window_in_force(self, test_db, org_with_old_and_new_row):
        org_id, _ = org_with_old_and_new_row
        _set_retention(test_db, org_id, 1095)

        with _ee(), _plan_retention(400):
            delete_organization(test_db, org_id)

        org = _org(test_db, org_id)
        assert org.deleted_at is not None
        assert org.settings.audit_log.retention_days_at_deletion == 400

    def test_rows_go_when_the_frozen_window_ends_even_without_a_licence(
        self, test_db, org_with_old_and_new_row
    ):
        org_id, boundary = org_with_old_and_new_row
        _set_retention(test_db, org_id, 90)
        with _ee():
            delete_organization(test_db, org_id)
        # A later, longer choice does not apply to a deleted org.
        _set_retention(test_db, org_id, 3650)

        assert _purge(test_db, org_id, boundary + timedelta(days=89), licensed=False) == 0
        assert _purge(test_db, org_id, boundary + timedelta(days=90), licensed=False) == 1

    def test_deleted_without_a_snapshot_uses_its_stored_choice(
        self, test_db, org_with_old_and_new_row
    ):
        org_id, boundary = org_with_old_and_new_row
        _set_retention(test_db, org_id, 90)
        org = _org(test_db, org_id)
        org.soft_delete()
        test_db.flush()

        assert _purge(test_db, org_id, boundary + timedelta(days=90), licensed=False) == 1


class TestJob:
    def test_does_nothing_without_the_audit_log(self):
        with patch.object(FeatureRegistry, "is_registered", return_value=False):
            assert job.sweep_expired_audit_events() == {"enabled": False}

    def test_one_orgs_failure_does_not_stop_the_rest(self):
        first, second = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())

        def purge(org, now):
            if org is first:
                raise RuntimeError("boom")
            return 3

        with (
            patch.object(job, "_organizations", return_value=[first, second]),
            patch.object(job, "_purge_organization", side_effect=purge),
            patch.object(job, "_clean_exports", return_value=0),
        ):
            result = job.sweep_expired_audit_events()

        assert result == {
            "enabled": True,
            "events_purged": 3,
            "orgs_purged": 1,
            "orgs_failed": 1,
            "export_files_deleted": 0,
            "export_cleanups_failed": 0,
        }

    def test_purges_an_org_on_its_own_session(self, real_commit_test_db, test_org_id):
        """The real path: a fresh session, scoped by the job, committing the purge."""
        db = real_commit_test_db
        _insert(db, test_org_id, "endpoint.created", T0)
        db.commit()
        boundary = _clock(db)
        org = _org(db, test_org_id)
        assert retention_days(org) == 365

        real_datetime = job.datetime

        class _Later(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return boundary + timedelta(days=365)

        with (
            _ee(),
            patch.object(job, "_organizations", return_value=[org]),
            patch.object(job, "datetime", _Later),
        ):
            result = job.sweep_expired_audit_events()

        assert result["orgs_failed"] == 0
        assert result["events_purged"] >= 1
        db.rollback()
        with as_org(db, test_org_id):
            left = db.execute(
                text(
                    "SELECT count(*) FROM audit_event WHERE organization_id = CAST(:org AS uuid) "
                    "AND recorded_at < :boundary AND action <> 'audit_log.purged'"
                ),
                {"org": test_org_id, "boundary": boundary},
            ).scalar_one()
        assert left == 0

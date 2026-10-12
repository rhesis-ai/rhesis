"""``audit_event`` is append-only at the database.

Two layers, each tested on its own. As the non-owner app role (``rhesis-app``,
like production's ``rhesis-user``) UPDATE, DELETE and TRUNCATE fail on
privileges. As the owner (a superuser here, like local dev) they fail on the
trigger. Without the first set, a local superuser would hide a missing REVOKE.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.backend.fixtures.database import admin_engine, test_engine

pytestmark = pytest.mark.security

_PURGE = (
    "SELECT audit_event_purge(CAST(:org AS uuid), CAST(:before AS timestamptz), 'a', 'b', NULL)"
)


@contextmanager
def _transaction(engine, org_id=None):
    """A connection whose work is always rolled back."""
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            if org_id is not None:
                _bind_org(conn, org_id)
            yield conn
        finally:
            trans.rollback()


def _bind_org(conn, org_id) -> None:
    conn.execute(
        text("SELECT set_config('app.current_organization', :org, true)"), {"org": str(org_id)}
    )


def _insert(conn, org_id, **overrides) -> UUID:
    row = {
        "org": str(org_id),
        "occurred_at": datetime.now(timezone.utc),
        "recorded_at": None,
        "action": "endpoint.updated",
    }
    row.update(overrides)
    return conn.execute(
        text(
            "INSERT INTO audit_event (organization_id, occurred_at, recorded_at, action, "
            "outcome, actor_type, channel, trace_id, span_id) "
            "VALUES (CAST(:org AS uuid), :occurred_at, "
            "COALESCE(:recorded_at, clock_timestamp()), :action, "
            "'success', 'user', 'web', 'a', 'b') RETURNING id"
        ),
        row,
    ).scalar_one()


def _fails(conn, statement: str, match: str, params=None) -> None:
    nested = conn.begin_nested()
    with pytest.raises(DBAPIError, match=match):
        conn.execute(text(statement), params or {})
    nested.rollback()


class TestAppendOnly:
    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE audit_event SET action = 'endpoint.deleted'",
            "DELETE FROM audit_event",
            "TRUNCATE audit_event",
        ],
    )
    def test_app_role_lacks_the_privilege(self, statement):
        org = uuid4()
        with _transaction(test_engine, org) as conn:
            _insert(conn, org)
            _fails(conn, statement, "permission denied")

    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE audit_event SET action = 'endpoint.deleted'",
            "DELETE FROM audit_event",
            "TRUNCATE audit_event",
        ],
    )
    def test_trigger_stops_the_owner(self, statement):
        org = uuid4()
        with _transaction(admin_engine, org) as conn:
            _insert(conn, org)
            _fails(conn, statement, "append-only")

    def test_app_role_can_insert_and_read(self):
        org = uuid4()
        with _transaction(test_engine, org) as conn:
            event_id = _insert(conn, org)
            assert conn.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 1
            assert event_id.version == 7

    def test_recorded_at_cannot_be_backdated(self):
        org = uuid4()
        backdated = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with _transaction(test_engine, org) as conn:
            event_id = _insert(conn, org, recorded_at=backdated)
            recorded_at = conn.execute(
                text("SELECT recorded_at FROM audit_event WHERE id = :id"), {"id": event_id}
            ).scalar_one()
        assert recorded_at > datetime.now(timezone.utc) - timedelta(minutes=5)

    def test_ids_sort_by_time(self):
        org = uuid4()
        with _transaction(test_engine, org) as conn:
            ids = [_insert(conn, org) for _ in range(3)]
            conn.execute(text("SELECT pg_sleep(0.002)"))
            ids.append(_insert(conn, org))
        assert ids[-1] > ids[0]


class TestTenantIsolation:
    def test_other_orgs_rows_are_invisible(self):
        mine, theirs = uuid4(), uuid4()
        with _transaction(admin_engine) as conn:
            _insert(conn, theirs)
            # Same transaction, so the row is visible to RLS rather than just uncommitted.
            conn.execute(text('SET LOCAL ROLE "rhesis-app"'))
            _bind_org(conn, mine)
            _insert(conn, mine)
            orgs = conn.execute(text("SELECT organization_id FROM audit_event")).scalars()
            assert set(orgs) == {mine}

    def test_cannot_insert_for_another_org(self):
        with _transaction(test_engine, uuid4()) as conn:
            nested = conn.begin_nested()
            with pytest.raises(DBAPIError, match="row-level security"):
                _insert(conn, uuid4())
            nested.rollback()


class TestPurge:
    def test_deletes_old_rows_of_one_org_and_records_itself(self):
        org, other = uuid4(), uuid4()
        with _transaction(test_engine, org) as conn:
            for _ in range(3):
                _insert(conn, org)
            _bind_org(conn, other)
            _insert(conn, other)
            _bind_org(conn, org)

            cutoff = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
            purged = conn.execute(text(_PURGE), {"org": str(org), "before": cutoff}).scalar_one()
            assert purged == 3

            rows = conn.execute(text("SELECT action, changes FROM audit_event")).all()
            assert [r.action for r in rows] == ["audit_log.purged"]
            assert rows[0].changes["count"] == 3

            # The caller's org binding survives the call.
            bound = conn.execute(text("SELECT current_setting('app.current_organization')"))
            assert bound.scalar_one() == str(org)

            _bind_org(conn, other)
            assert conn.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 1

    def test_does_not_leave_deletes_open(self):
        org = uuid4()
        with _transaction(admin_engine, org) as conn:
            _insert(conn, org)
            cutoff = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
            conn.execute(text(_PURGE), {"org": str(org), "before": cutoff})
            _fails(conn, "DELETE FROM audit_event", "append-only")

    def test_rejects_a_future_cutoff(self):
        org = uuid4()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        with _transaction(test_engine, org) as conn:
            _fails(conn, _PURGE, "in the future", {"org": str(org), "before": future})

    def test_only_the_app_role_may_execute(self):
        with _transaction(admin_engine) as conn:
            grantees = set(
                conn.execute(
                    text(
                        "SELECT acl.grantee FROM pg_proc "
                        "CROSS JOIN LATERAL aclexplode(proacl) acl "
                        "WHERE proname = 'audit_event_purge'"
                    )
                ).scalars()
            )
            app_role = conn.execute(
                text("SELECT oid FROM pg_roles WHERE rolname = 'rhesis-app'")
            ).scalar_one()
        assert 0 not in grantees, "PUBLIC must not execute the purge function"
        assert app_role in grantees


class TestShape:
    def test_has_no_foreign_keys(self):
        """Deleting an org, project, user or job must neither cascade into
        the log nor be blocked by it."""
        with _transaction(admin_engine) as conn:
            count = conn.execute(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid = 'audit_event'::regclass AND contype = 'f'"
                )
            ).scalar_one()
        assert count == 0

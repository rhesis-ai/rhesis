"""FORCE RLS suspension for a migration owner without BYPASSRLS.

On managed Postgres the owner can't have BYPASSRLS, so ``alembic/env.py`` lifts
FORCE on the owner's tables while migrating and puts it back before each commit.
These tests run the helper as such an owner, against tables in public with a
unique prefix, and check FORCE is back whenever a transaction commits.
"""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from rhesis.backend.alembic.utils.force_rls import suspend_force_rls_for_owner
from rhesis.backend.app.config.settings import get_database_settings

_PASSWORD = "force-rls-test"  # trufflehog:ignore


@pytest.fixture
def owner():
    """A NOBYPASSRLS role owning ``<prefix>_t``, with FORCE RLS on and a tenant policy."""
    admin_url = get_database_settings().admin_url
    superuser = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    # Hyphenated, like rhesis-admin, so unquoted names fail here too.
    role = f"force-rls-{uuid.uuid4().hex[:8]}"
    # The suspension only looks at public, so the tables go there under a prefix.
    schema = f"force_rls_{uuid.uuid4().hex[:8]}"
    with superuser.connect() as conn:
        conn.execute(sa.text(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{_PASSWORD}' NOBYPASSRLS"))
        conn.execute(sa.text(f'GRANT CREATE ON SCHEMA public TO "{role}"'))
    engine = sa.create_engine(make_url(admin_url).set(username=role, password=_PASSWORD))
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE {schema}_t (organization_id uuid)"))
        conn.execute(sa.text(f"ALTER TABLE {schema}_t ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {schema}_t FORCE ROW LEVEL SECURITY"))
        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {schema}_t USING "
                "(organization_id = current_setting('app.current_organization')::uuid)"
            )
        )
    try:
        yield engine, schema, superuser
    finally:
        engine.dispose()
        with superuser.connect() as conn:
            conn.execute(sa.text(f'DROP OWNED BY "{role}" CASCADE'))
            conn.execute(sa.text(f'DROP ROLE "{role}"'))
        superuser.dispose()


def _forced(superuser, table: str) -> bool:
    with superuser.connect() as conn:
        return conn.execute(
            sa.text("SELECT relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:t)"),
            {"t": table},
        ).scalar_one()


def _seed(conn, table: str) -> None:
    # Unscoped write: fails under FORCE with no org bound.
    conn.execute(sa.text(f"INSERT INTO {table} VALUES (NULL)"))


def test_without_suspension_unscoped_write_fails(owner):
    engine, schema, _ = owner
    with engine.connect() as conn, pytest.raises(sa.exc.ProgrammingError):
        with conn.begin():
            _seed(conn, f"{schema}_t")


def test_force_is_lifted_inside_the_transaction_and_back_after_commit(owner):
    engine, schema, superuser = owner
    with engine.connect() as conn:
        assert suspend_force_rls_for_owner(conn) is not None
        with conn.begin():
            _seed(conn, f"{schema}_t")
    assert _forced(superuser, f"{schema}_t")


def test_rollback_leaves_force_on(owner):
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        with pytest.raises(RuntimeError), conn.begin():
            _seed(conn, f"{schema}_t")
            raise RuntimeError("migration failed")
    assert _forced(superuser, f"{schema}_t")


def test_mid_run_commit_restores_force_and_next_transaction_lifts_it(owner):
    """The commit/begin pair ``autocommit_block()`` makes partway through a run."""
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        conn.begin()
        _seed(conn, f"{schema}_t")
        conn.commit()
        assert _forced(superuser, f"{schema}_t")
        conn.execution_options(isolation_level="AUTOCOMMIT")
        with conn.begin():
            conn.execute(sa.text("SELECT 1"))
        assert _forced(superuser, f"{schema}_t")
        conn.execution_options(isolation_level="READ COMMITTED")
        with conn.begin():
            _seed(conn, f"{schema}_t")
    assert _forced(superuser, f"{schema}_t")


def test_table_a_migration_forces_can_be_seeded_in_the_same_migration(owner):
    """New tables FORCE RLS in their own migration and may seed straight after."""
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        with conn.begin():
            conn.execute(sa.text(f"CREATE TABLE {schema}_new (organization_id uuid)"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_new ENABLE ROW LEVEL SECURITY"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_new FORCE ROW LEVEL SECURITY"))
            _seed(conn, f"{schema}_new")
            conn.execute(sa.text(f"ALTER TABLE {schema}_new RENAME TO {schema}_renamed"))
    assert _forced(superuser, f"{schema}_renamed")


def test_after_step_hook_catches_force_the_statement_text_hides(owner):
    engine, schema, superuser = owner
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                f"CREATE FUNCTION {schema}_lock_down() RETURNS void LANGUAGE plpgsql AS "
                f"$$ BEGIN EXECUTE 'ALTER TABLE {schema}_new ' || 'FORCE ROW LEVEL ' || "
                "'SECURITY'; END $$"
            )
        )
    with engine.connect() as conn:
        after_step = suspend_force_rls_for_owner(conn)
        with conn.begin():
            conn.execute(sa.text(f"CREATE TABLE {schema}_new (organization_id uuid)"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_new ENABLE ROW LEVEL SECURITY"))
            conn.execute(sa.text(f"SELECT {schema}_lock_down()"))
            after_step()
            _seed(conn, f"{schema}_new")
    assert _forced(superuser, f"{schema}_new")


def test_explicit_no_force_in_a_migration_is_kept(owner):
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        with conn.begin():
            conn.execute(sa.text(f"ALTER TABLE {schema}_t NO FORCE ROW LEVEL SECURITY"))
    assert not _forced(superuser, f"{schema}_t")


def test_no_force_from_dynamic_sql_is_kept(owner):
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        with conn.begin():
            conn.execute(
                sa.text(
                    "DO $$ BEGIN EXECUTE format("
                    f"'ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', '{schema}_t'); END $$"
                )
            )
    assert not _forced(superuser, f"{schema}_t")


def test_no_force_on_one_table_leaves_the_others_restored(owner):
    engine, schema, superuser = owner
    with engine.connect() as conn:
        suspend_force_rls_for_owner(conn)
        with conn.begin():
            conn.execute(sa.text(f"CREATE TABLE {schema}_other (organization_id uuid)"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_other ENABLE ROW LEVEL SECURITY"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_other FORCE ROW LEVEL SECURITY"))
            conn.execute(sa.text(f"ALTER TABLE {schema}_t NO FORCE ROW LEVEL SECURITY"))
            _seed(conn, f"{schema}_other")
    assert not _forced(superuser, f"{schema}_t")
    assert _forced(superuser, f"{schema}_other")


def test_role_that_bypasses_rls_is_left_alone():
    engine = sa.create_engine(get_database_settings().admin_url)
    try:
        with engine.connect() as conn:
            assert suspend_force_rls_for_owner(conn) is None
    finally:
        engine.dispose()


def test_tables_outside_public_are_left_alone(owner):
    engine, schema, superuser = owner
    with superuser.connect() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA {schema} AUTHORIZATION "{engine.url.username}"'))
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(f"ALTER TABLE {schema}_t SET SCHEMA {schema}"))
        with engine.connect() as conn:
            suspend_force_rls_for_owner(conn)
            with conn.begin():
                forced = conn.execute(
                    sa.text("SELECT relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:t)"),
                    {"t": f"{schema}.{schema}_t"},
                ).scalar_one()
        assert forced
    finally:
        with superuser.connect() as conn:
            conn.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))

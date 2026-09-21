"""Postgres/Redis containers for the backend test session.

Must run before any backend/app module is imported — tests.backend.fixtures.database
reads DB_HOST/DB_PORT to build its module-level engine at import time.

One container pair is shared by every pytest-xdist worker. The xdist controller
imports this module before it spawns workers, so it starts the containers,
migrates a template database once, and exports the connection details into its
own environment. Workers inherit that environment and start nothing; each
clones the template into a database of its own with ``CREATE DATABASE ...
TEMPLATE``, which is a file copy rather than a 269-revision migration replay.

Two hazards this has to respect, both of which are why the old code gave every
worker its own pair:

- A container handle only works in the process that created it. Nothing is
  passed between processes except host/port strings, and only the process that
  started a container ever stops it.
- A worker must not tear down containers its siblings are still using. Only the
  starting process registers the atexit hook, and it outlives every worker.
"""

from __future__ import annotations

import atexit
import os

ADMIN_USER = "rhesis-user"
ADMIN_PASS = "your-secured-password"  # trufflehog:ignore
APP_USER = "rhesis-app"
APP_PASS = "rhesis-app-pass"  # trufflehog:ignore

#: Migrated once, then cloned per worker. Never connected to by a test.
TEMPLATE_DB = "rhesis-test-template"

#: Set by whichever process starts the containers; inherited by xdist workers.
_ENV_DB_HOST = "RHESIS_TEST_DB_HOST"
_ENV_DB_PORT = "RHESIS_TEST_DB_PORT"
_ENV_REDIS_HOST = "RHESIS_TEST_REDIS_HOST"
_ENV_REDIS_PORT = "RHESIS_TEST_REDIS_PORT"


def _connect(host: str, port: str, dbname: str):
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=int(port),
        dbname=dbname,
        user=ADMIN_USER,
        password=ADMIN_PASS,
    )
    conn.autocommit = True
    return conn


def _create_app_role(host: str, port: str, dbname: str) -> None:
    """Create the non-BYPASSRLS app role that mirrors production.

    Production runs ``rhesis-user`` with ``bypassrls: false``; the test
    container makes its initial user a superuser (Postgres default). This
    creates a second role for the app layer so RLS is enforced in tests the
    same way it is in production.

    Roles are cluster-wide, so this runs once. The grants below are per
    database and are applied to the template, which means every clone inherits
    them without repeating the work.
    """
    conn = _connect(host, port, dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'CREATE ROLE "rhesis-app" LOGIN PASSWORD %s NOBYPASSRLS',
                (APP_PASS,),
            )
            cur.execute('GRANT USAGE ON SCHEMA public TO "rhesis-app"')
            cur.execute(
                'ALTER DEFAULT PRIVILEGES FOR ROLE "rhesis-user" IN SCHEMA public '
                'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "rhesis-app"'
            )
            cur.execute(
                'ALTER DEFAULT PRIVILEGES FOR ROLE "rhesis-user" IN SCHEMA public '
                'GRANT USAGE, SELECT ON SEQUENCES TO "rhesis-app"'
            )
    finally:
        conn.close()


def grant_app_role_privileges(host: str, port: str, dbname: str) -> None:
    """Grant the app role access to all existing tables and sequences.

    Called against the template after migrations, to catch anything
    ``ALTER DEFAULT PRIVILEGES`` did not cover (e.g. tables created by
    extensions or event triggers that don't fire under the migration role's
    default-privilege scope). Clones inherit the result.
    """
    conn = _connect(host, port, dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                'ON ALL TABLES IN SCHEMA public TO "rhesis-app"'
            )
            cur.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "rhesis-app"')
    finally:
        conn.close()


#: Arbitrary int64, shared by every process cloning from this template.
_CLONE_LOCK_KEY = 0x5268657369735F31


def clone_template_database(host: str, port: str, target: str) -> None:
    """Create *target* as a copy of the migrated template.

    Runs from the ``postgres`` maintenance database, not the template: Postgres
    refuses to copy a template that has any other session connected to it, and
    our own connection would count. Two concurrent copies of one template also
    collide, so this serialises on an advisory lock. Workers call it once each,
    so that is a handful of short waits.
    """
    conn = _connect(host, port, "postgres")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_CLONE_LOCK_KEY,))
            try:
                cur.execute(f'DROP DATABASE IF EXISTS "{target}"')
                cur.execute(f'CREATE DATABASE "{target}" TEMPLATE "{TEMPLATE_DB}"')
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_CLONE_LOCK_KEY,))
    finally:
        conn.close()


def _template_is_migrated(conn) -> bool:
    """True when the template already carries an Alembic version row."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        if not cur.fetchone()[0]:
            return False
        cur.execute("SELECT count(*) FROM alembic_version")
        return cur.fetchone()[0] > 0


def ensure_template_migrated(host: str, port: str, migrate) -> None:
    """Run *migrate* against the template unless it is already at head.

    The check and the migration happen under one advisory lock, so when
    several workers reach this at once exactly one migrates and the rest wait
    and then find the work done. In the normal case the xdist controller has
    already migrated before any worker starts, and every worker takes the
    cheap path.
    """
    conn = _connect(host, port, TEMPLATE_DB)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_MIGRATE_LOCK_KEY,))
        try:
            if _template_is_migrated(conn):
                return
            migrate()
            grant_app_role_privileges(host, port, TEMPLATE_DB)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATE_LOCK_KEY,))
    finally:
        conn.close()


#: Distinct from the clone lock: a worker may clone while nothing is migrating.
_MIGRATE_LOCK_KEY = 0x5268657369735F32


def _containers_from_env() -> dict | None:
    """Connection details exported by the process that started the containers."""
    host = os.environ.get(_ENV_DB_HOST)
    if not host:
        return None
    return {
        "db_host": host,
        "db_port": os.environ[_ENV_DB_PORT],
        "redis_host": os.environ[_ENV_REDIS_HOST],
        "redis_port": os.environ[_ENV_REDIS_PORT],
    }


def ensure_test_containers() -> dict:
    """Start the shared Postgres/Redis pair, or reuse the one already running.

    Returns a dict with ``db_host``/``db_port``/``redis_host``/``redis_port``.
    """
    existing = _containers_from_env()
    if existing is not None:
        return existing

    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    postgres = PostgresContainer(
        image="mirror.gcr.io/pgvector/pgvector:pg16",
        username=ADMIN_USER,
        password=ADMIN_PASS,
        dbname=TEMPLATE_DB,
    )
    # Every worker's database lives in this one server now, so the old
    # per-worker connection budget has to cover all of them at once.
    postgres.with_command("postgres -c max_connections=400")
    postgres.with_kwargs(tmpfs={"/var/lib/postgresql/data": "rw"})
    postgres.start()
    atexit.register(postgres.stop)

    db_host = postgres.get_container_host_ip()
    db_port = str(postgres.get_exposed_port(5432))

    _create_app_role(db_host, db_port, TEMPLATE_DB)

    redis = RedisContainer(
        image="mirror.gcr.io/redis:7-alpine",
        password="rhesis-redis-pass",
    )
    redis.start()
    atexit.register(redis.stop)

    containers = {
        "db_host": db_host,
        "db_port": db_port,
        "redis_host": redis.get_container_host_ip(),
        "redis_port": str(redis.get_exposed_port(6379)),
    }

    # Exported rather than returned, so xdist workers inherit them and skip
    # everything above.
    os.environ[_ENV_DB_HOST] = containers["db_host"]
    os.environ[_ENV_DB_PORT] = containers["db_port"]
    os.environ[_ENV_REDIS_HOST] = containers["redis_host"]
    os.environ[_ENV_REDIS_PORT] = containers["redis_port"]

    return containers

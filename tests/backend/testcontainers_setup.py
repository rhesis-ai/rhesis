"""Ephemeral Postgres/Redis containers for the backend test session.

Must run before any backend/app module is imported — tests.backend.fixtures.database
reads DB_HOST/DB_PORT to build its module-level engine at import time.

Each pytest-xdist worker starts its own container pair rather than sharing one:
a container handle only works in the process that created it, and a shared
container risks a worker tearing it down mid-test for its siblings.
"""

from __future__ import annotations

import atexit

ADMIN_USER = "rhesis-user"
ADMIN_PASS = "your-secured-password"  # trufflehog:ignore
APP_USER = "rhesis-app"
APP_PASS = "rhesis-app-pass"  # trufflehog:ignore


def _create_app_role(host: str, port: str, dbname: str) -> None:
    """Create the non-BYPASSRLS app role that mirrors production.

    Production runs ``rhesis-user`` with ``bypassrls: false``; the test
    container makes its initial user a superuser (Postgres default). This
    creates a second role for the app layer so RLS is enforced in tests the
    same way it is in production.

    ``ALTER DEFAULT PRIVILEGES`` ensures tables created by future migrations
    are automatically accessible to the app role.
    """
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=int(port),
        dbname=dbname,
        user=ADMIN_USER,
        password=ADMIN_PASS,
    )
    conn.autocommit = True
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

    Called after migrations to catch anything ``ALTER DEFAULT PRIVILEGES``
    did not cover (e.g. tables created by extensions or event triggers that
    don't fire under the migration role's default-privilege scope).
    """
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=int(port),
        dbname=dbname,
        user=ADMIN_USER,
        password=ADMIN_PASS,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                'ON ALL TABLES IN SCHEMA public TO "rhesis-app"'
            )
            cur.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "rhesis-app"')
    finally:
        conn.close()


def ensure_test_containers() -> dict:
    """Start this process's own Postgres/Redis containers.

    Returns a dict with ``db_host``/``db_port``/``redis_host``/``redis_port``.
    """
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    postgres = PostgresContainer(
        image="mirror.gcr.io/pgvector/pgvector:pg16",
        username=ADMIN_USER,
        password=ADMIN_PASS,
        dbname="rhesis-test-db",
    )
    postgres.with_command("postgres -c max_connections=200")
    postgres.with_kwargs(tmpfs={"/var/lib/postgresql/data": "rw"})
    postgres.start()
    atexit.register(postgres.stop)

    db_host = postgres.get_container_host_ip()
    db_port = postgres.get_exposed_port(5432)

    _create_app_role(db_host, str(db_port), "rhesis-test-db")

    redis = RedisContainer(
        image="mirror.gcr.io/redis:7-alpine",
        password="rhesis-redis-pass",
    )
    redis.start()
    atexit.register(redis.stop)

    return {
        "db_host": db_host,
        "db_port": db_port,
        "redis_host": redis.get_container_host_ip(),
        "redis_port": redis.get_exposed_port(6379),
    }

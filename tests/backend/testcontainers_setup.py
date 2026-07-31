"""Ephemeral Postgres/Redis containers for the backend test session.

Must run before any backend/app module is imported — tests.backend.fixtures.database
reads DB_HOST/DB_PORT to build its module-level engine at import time.

Each pytest-xdist worker starts its own container pair rather than sharing one:
a container handle only works in the process that created it, and a shared
container risks a worker tearing it down mid-test for its siblings.
"""

from __future__ import annotations

import atexit


def ensure_test_containers() -> dict:
    """Start this process's own Postgres/Redis containers.

    Returns a dict with ``db_host``/``db_port``/``redis_host``/``redis_port``.
    """
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    postgres = PostgresContainer(
        image="mirror.gcr.io/pgvector/pgvector:pg16",
        username="rhesis-user",
        password="your-secured-password",  # trufflehog:ignore
        dbname="rhesis-test-db",
    )
    postgres.with_command("postgres -c max_connections=200")
    postgres.with_kwargs(tmpfs={"/var/lib/postgresql/data": "rw"})
    postgres.start()
    atexit.register(postgres.stop)

    redis = RedisContainer(
        image="mirror.gcr.io/redis:7-alpine",
        password="rhesis-redis-pass",
    )
    redis.start()
    atexit.register(redis.stop)

    return {
        "db_host": postgres.get_container_host_ip(),
        "db_port": postgres.get_exposed_port(5432),
        "redis_host": redis.get_container_host_ip(),
        "redis_port": redis.get_exposed_port(6379),
    }

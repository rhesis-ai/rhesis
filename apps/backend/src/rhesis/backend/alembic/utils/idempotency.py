"""Idempotency helpers for Alembic upgrade() functions.

Import and call these instead of inlining information_schema / pg_indexes
queries in each migration file.
"""

import sqlalchemy as sa


def column_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).fetchone()
        is not None
    )


def table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        ).fetchone()
        is not None
    )


def index_exists(conn, index_name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"),
            {"n": index_name},
        ).fetchone()
        is not None
    )


def fk_exists(conn, constraint_name: str, table: str) -> bool:
    return (
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE constraint_schema = 'public' "
                "AND constraint_name = :n AND table_name = :t"
            ),
            {"n": constraint_name, "t": table},
        ).fetchone()
        is not None
    )

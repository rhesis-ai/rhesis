#!/usr/bin/env python
"""Check that a fresh install migrates on managed Postgres (RDS, Cloud SQL, Azure).

Managed Postgres has no SUPERUSER, and on PG16 only a BYPASSRLS role can grant
BYPASSRLS, so there the migration owner runs without it. This script migrates
two fresh databases on one server and compares them:

- ``bypass``: owner has BYPASSRLS, like our own production.
- ``nobypass``: owner has neither SUPERUSER nor BYPASSRLS, like RDS.

Both get the extensions a managed-Postgres admin pre-creates (``uuid-ossp``,
``vector``) plus ``pg_stat_statements``, which RDS installs in ``public``. After
``alembic upgrade head`` it diffs, read as the superuser:

- ``relrowsecurity`` / ``relforcerowsecurity`` of every table
- ``pg_policies``
- row count and a content digest of every table (uuid and timestamp columns
  left out, since those differ between any two installs)

Exits non-zero if either upgrade fails or anything differs.

Needs a Postgres 16 server and a superuser to set it up, read from the usual
libpq variables (default ``postgres@localhost:5432``)::

    docker run -d --name rls-check -p 55432:5432 -e POSTGRES_PASSWORD=postgres \\
        pgvector/pgvector:pg16
    cd apps/backend
    PGPORT=55432 PGPASSWORD=postgres uv run --extra all --extra cpu \\
        python scripts/check_managed_postgres_migrations.py

``--only nobypass`` runs just the RDS-like upgrade; ``--keep`` leaves the
databases in place for inspection.
"""

from __future__ import annotations

import argparse
import difflib
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql

HOST = os.environ.get("PGHOST", "localhost")
PORT = os.environ.get("PGPORT", "5432")
SUPERUSER = os.environ.get("PGUSER", "postgres")
SUPERPASS = os.environ.get("PGPASSWORD", "postgres")

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "src" / "rhesis" / "backend"
OWNER_PASS = "rls-check-owner"  # trufflehog:ignore
SCENARIOS = {"bypass": "BYPASSRLS", "nobypass": "NOBYPASSRLS"}
EXTENSIONS = ['"uuid-ossp"', "vector", "pg_stat_statements"]

# Differ between any two installs even when the seed data is the same.
_VOLATILE_TYPES = ("uuid", "timestamp with time zone", "timestamp without time zone")
_VOLATILE_COLUMNS = ("nano_id",)


def _names(scenario: str) -> tuple[str, str]:
    # Hyphens like rhesis-db / rhesis-admin, so unquoted-name bugs show up here.
    return f"rls-check-{scenario}", f"rls-check-{scenario}-owner"


def _connect(dbname: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST,
        port=int(PORT),
        user=SUPERUSER,
        password=SUPERPASS,
        dbname=dbname,
        autocommit=True,
    )


def _drop(scenario: str) -> None:
    db, owner = _names(scenario)
    with _connect("postgres") as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db)))
        conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(owner)))


def _create(scenario: str) -> None:
    db, owner = _names(scenario)
    _drop(scenario)
    with _connect("postgres") as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB {}").format(
                sql.Identifier(owner), sql.Literal(OWNER_PASS), sql.SQL(SCENARIOS[scenario])
            )
        )
        conn.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(db), sql.Identifier(owner))
        )
    with _connect(db) as conn:
        for ext in EXTENSIONS:
            conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext} SCHEMA public")


def _migrate(scenario: str) -> bool:
    db, owner = _names(scenario)
    env = dict(os.environ)
    env.update(
        {
            "BACKEND_ENV": "production",
            "DB_DRIVER": "postgresql+psycopg",
            "DB_HOST": HOST,
            "DB_PORT": PORT,
            "DB_NAME": db,
            "ADMIN_DB_USER": owner,
            "ADMIN_DB_PASS": OWNER_PASS,
            "OTEL_RHESIS_TELEMETRY_ENABLED": "false",
        }
    )
    # Some migrations import app modules that build the runtime engine at import
    # time; they still write through the migration connection.
    env["APP_DB_USER"] = owner
    env["APP_DB_PASS"] = OWNER_PASS
    # Throwaway databases: any valid Fernet key will do.
    env.setdefault("DB_ENCRYPTION_KEY", "cmhlc2lzLXJscy1jaGVjay1rZXktMzItYnl0ZXMhISE=")
    print(f"\n>>> [{scenario}] alembic upgrade head as {owner} ({SCENARIOS[scenario]})", flush=True)
    # This interpreter's alembic, so `uv run` can't re-sync the venv without extras.
    alembic = str(Path(sys.executable).with_name("alembic"))
    result = subprocess.run([alembic, "upgrade", "head"], cwd=ALEMBIC_DIR, env=env)
    return result.returncode == 0


def _snapshot(scenario: str) -> dict[str, list[str]]:
    db, owner = _names(scenario)
    with _connect(db) as conn:
        rls = [
            f"{name} enable={enabled} force={forced}"
            for name, enabled, forced in conn.execute(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p') "
                "ORDER BY relname"
            )
        ]
        policies = [
            " | ".join(str(v) for v in row).replace(owner, "<owner>")
            for row in conn.execute(
                "SELECT tablename, policyname, permissive, roles::text, cmd, qual, with_check "
                "FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname"
            )
        ]
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT c.relname FROM pg_class c "
                "WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') "
                "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid "
                "AND d.deptype = 'e') ORDER BY c.relname"
            )
        ]
        rows = [_table_digest(conn, table) for table in tables]
        version = [r[0] for r in conn.execute("SELECT version_num FROM alembic_version")]
    return {"rls": rls, "policies": policies, "rows": rows, "alembic_version": version}


def _table_digest(conn: psycopg.Connection, table: str) -> str:
    columns = [
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "AND data_type <> ALL(%s) AND column_name <> ALL(%s) ORDER BY column_name",
            (table, list(_VOLATILE_TYPES), list(_VOLATILE_COLUMNS)),
        )
    ]
    row_text = (
        sql.SQL("concat_ws('|', {})").format(
            sql.SQL(", ").join(sql.SQL("{}::text").format(sql.Identifier(c)) for c in columns)
        )
        if columns
        else sql.SQL("''")
    )
    query = sql.SQL(
        "SELECT count(*), coalesce(md5(string_agg(r, E'\\n' ORDER BY r)), '-') "
        "FROM (SELECT {} AS r FROM {}) t"
    ).format(row_text, sql.Identifier(table))
    count, digest = conn.execute(query).fetchone()
    return f"{table} rows={count} digest={digest}"


def _diff(a: dict[str, list[str]], b: dict[str, list[str]]) -> bool:
    identical = True
    for key in a:
        if a[key] == b[key]:
            print(f"    {key}: identical ({len(a[key])} entries)")
            continue
        identical = False
        print(f"    {key}: DIFFERENT")
        for line in difflib.unified_diff(a[key], b[key], "bypass", "nobypass", lineterm=""):
            print(f"      {line}")
    return identical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=sorted(SCENARIOS))
    parser.add_argument("--keep", action="store_true", help="leave the databases in place")
    args = parser.parse_args()
    scenarios = [args.only] if args.only else list(SCENARIOS)

    failed = []
    try:
        for scenario in scenarios:
            _create(scenario)
            if not _migrate(scenario):
                failed.append(scenario)
        if failed:
            print(f"\nFAILED: alembic upgrade head failed for {', '.join(failed)}")
            return 1
        if len(scenarios) == 1:
            print(f"\nOK: {scenarios[0]} migrated to head")
            return 0
        print("\n>>> comparing bypass vs nobypass")
        if not _diff(_snapshot("bypass"), _snapshot("nobypass")):
            print("\nFAILED: the two installs differ")
            return 1
        print("\nOK: both migrated to head with identical RLS state, policies and data")
        return 0
    finally:
        if not args.keep:
            for scenario in scenarios:
                _drop(scenario)


if __name__ == "__main__":
    sys.exit(main())

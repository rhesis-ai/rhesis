#!/usr/bin/env python
"""Simulate the Cloud SQL migration environment locally.

The dev Cloud SQL migrate job runs alembic as a role that is NOT superuser and
NOT BYPASSRLS, and that owns the tables. That combination is what makes
RLS-sensitive migrations (e.g. a9b8c7d6e5f4) behave differently than on a local
superuser connection — PostgreSQL's FK initial-validation query runs under the
table owner's identity and is therefore subject to RLS.

This script reproduces that environment faithfully against a throwaway database
so a migration can be validated WITHOUT deploying:

  1. create a NOSUPERUSER / NOBYPASSRLS role + throwaway DB
  2. bring the DB to PRE_REV as the local superuser
  3. transfer ownership of the touched tables to the non-bypass role
  4. run `alembic upgrade TARGET_REV` AS the non-bypass role  <- the real test
  5. drop the DB and role

Usage:
    cd apps/backend
    uv run python scripts/sim_cloud_migration.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# --- configuration ---------------------------------------------------------
SUPER_USER = os.environ.get("SIM_SUPER_USER", "rhesis-user")
SUPER_PASS = os.environ.get("SIM_SUPER_PASS", "rhesis-password")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
MAINT_DB = os.environ.get("SIM_MAINT_DB", "rhesis-db")

SIM_DB = "rhesis_mig_sim"
SIM_ROLE = "mig_sim"
SIM_PW = "mig_sim_pw"

# The dev Cloud SQL migration role (nocodb-user) was granted BYPASSRLS, matching
# prod's rhesis-admin. Set to False to simulate the old non-bypass environment.
SIM_BYPASSRLS = os.environ.get("SIM_BYPASSRLS", "true").lower() in ("1", "true", "yes")

# Revision just before the migration under test, and the target to upgrade to.
PRE_REV = os.environ.get("SIM_PRE_REV", "b8c9d0e1f2a3")
TARGET_REV = os.environ.get("SIM_TARGET_REV", "head")

# Tables the migration under test touches; ownership is handed to the non-bypass
# role so FK validation + RLS behave exactly as on Cloud SQL. alembic_version is
# included so the role can record the revision bump.
TABLES = [
    "architect_message",
    "architect_session",
    "organization",
    '"user"',
    "alembic_version",
]

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "src" / "rhesis" / "backend"


def _url(user: str, pw: str, db: str) -> str:
    return f"postgresql://{user}:{pw}@{DB_HOST}:{DB_PORT}/{db}"


def _superengine(db: str):
    return create_engine(_url(SUPER_USER, SUPER_PASS, db), isolation_level="AUTOCOMMIT")


def _alembic_env(user: str, pw: str) -> dict[str, str]:
    env = dict(os.environ)
    # These take precedence over apps/backend/.env (load_dotenv does not override
    # variables already present in the environment).
    env["DB_DRIVER"] = "postgresql"
    env["DB_HOST"] = DB_HOST
    env["DB_PORT"] = DB_PORT
    env["DB_NAME"] = SIM_DB
    env["ADMIN_DB_USER"] = user
    env["ADMIN_DB_PASS"] = pw
    return env


def _run_alembic(user: str, pw: str, rev: str) -> None:
    print(f"\n>>> alembic upgrade {rev}  (as {user})", flush=True)
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", rev],
        cwd=ALEMBIC_DIR,
        env=_alembic_env(user, pw),
        check=True,
    )


def setup() -> None:
    print(">>> setup: create role + throwaway database", flush=True)
    with _superengine(MAINT_DB).connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{SIM_DB}" WITH (FORCE)'))
        c.execute(text(f'DROP ROLE IF EXISTS "{SIM_ROLE}"'))
        bypass = "BYPASSRLS" if SIM_BYPASSRLS else "NOBYPASSRLS"
        c.execute(
            text(
                f"CREATE ROLE \"{SIM_ROLE}\" LOGIN PASSWORD '{SIM_PW}' "
                f"NOSUPERUSER {bypass} NOCREATEDB"
            )
        )
        c.execute(text(f'CREATE DATABASE "{SIM_DB}" OWNER "{SIM_ROLE}"'))


def transfer_ownership() -> None:
    # On Cloud SQL the migration role owns every table (it created them), so make
    # the non-bypass role own all tables + sequences here too — not just the few
    # tables the migration under test names. This mirrors the FK-validation owner
    # switch and lets the whole remaining migration chain run as the role.
    print(">>> transfer ALL table/sequence ownership to the non-bypass role", flush=True)
    with _superengine(SIM_DB).connect() as c:
        c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{SIM_ROLE}"'))
        c.execute(text(f'GRANT CREATE ON SCHEMA public TO "{SIM_ROLE}"'))
        for (tbl,) in c.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).all():
            c.execute(text(f'ALTER TABLE public."{tbl}" OWNER TO "{SIM_ROLE}"'))
        for (seq,) in c.execute(
            text("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'")
        ).all():
            c.execute(text(f'ALTER SEQUENCE public."{seq}" OWNER TO "{SIM_ROLE}"'))
        # Confirm the role really is non-bypass / non-super (the whole point).
        row = c.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"),
            {"r": SIM_ROLE},
        ).one()
        print(f"    {SIM_ROLE}: rolsuper={row[0]} rolbypassrls={row[1]}", flush=True)


def teardown() -> None:
    print("\n>>> teardown: drop database + role", flush=True)
    with _superengine(MAINT_DB).connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{SIM_DB}" WITH (FORCE)'))
        c.execute(text(f'DROP ROLE IF EXISTS "{SIM_ROLE}"'))


def main() -> int:
    setup()
    try:
        # Phase 1: reach the pre-migration revision as the superuser.
        _run_alembic(SUPER_USER, SUPER_PASS, PRE_REV)
        # Phase 2: make the migration role own the touched tables.
        transfer_ownership()
        # Phase 3: the real test — run the migration as the non-bypass owner.
        _run_alembic(SIM_ROLE, SIM_PW, TARGET_REV)
    except subprocess.CalledProcessError as exc:
        print(
            f"\n❌ SIMULATION FAILED (exit {exc.returncode}) — "
            f"this migration would fail on Cloud SQL.",
            flush=True,
        )
        teardown()
        return 1
    role_desc = "BYPASSRLS" if SIM_BYPASSRLS else "non-bypass"
    print(f"\n✅ SIMULATION PASSED — migration runs as a {role_desc} table owner.", flush=True)
    teardown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

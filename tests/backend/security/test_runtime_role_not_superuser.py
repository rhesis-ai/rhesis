"""The app's runtime database role must be subject to row-level security.

A superuser or BYPASSRLS role skips every RLS policy, so tenant isolation would
rest on the application layer alone. The backend refuses to boot on such a role
outside local development; these tests pin both the harness role and that check.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from rhesis.backend.app.config.settings import ApplicationSettings
from rhesis.backend.app.database import (
    PrivilegedDatabaseRoleError,
    assert_runtime_role_restricted,
    engine,
    runtime_role_check_required,
)

pytestmark = pytest.mark.security


def _role_flags(conn) -> tuple[str, bool, bool]:
    return conn.execute(
        text(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    ).one()


def test_runtime_engine_role_is_not_superuser_and_not_bypassrls():
    with engine.connect() as conn:
        role, is_superuser, bypasses_rls = _role_flags(conn)
    assert role == "rhesis-app"
    assert not is_superuser
    assert not bypasses_rls


def test_check_accepts_runtime_role():
    with engine.connect() as conn:
        assert_runtime_role_restricted(conn)


def test_check_rejects_superuser(admin_test_db):
    with pytest.raises(PrivilegedDatabaseRoleError, match="superuser"):
        assert_runtime_role_restricted(admin_test_db)


def test_check_rejects_bypassrls_role(admin_test_db):
    role = f"bypass_{uuid.uuid4().hex[:12]}"
    admin_test_db.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER BYPASSRLS'))
    try:
        admin_test_db.execute(text(f'SET LOCAL ROLE "{role}"'))
        with pytest.raises(PrivilegedDatabaseRoleError, match="BYPASSRLS"):
            assert_runtime_role_restricted(admin_test_db)
    finally:
        admin_test_db.execute(text("RESET ROLE"))
        admin_test_db.execute(text(f'DROP ROLE "{role}"'))


@pytest.mark.parametrize(
    ("backend_env", "dev_mode", "required"),
    [
        ("production", False, True),
        ("staging", False, True),
        # Self-host (docker-compose) runs with BACKEND_ENV=local.
        ("local", False, True),
        # The ./rh dev stack runs the app as the Postgres superuser.
        ("local", True, False),
        ("development", False, False),
    ],
)
def test_check_required_outside_local_development(backend_env, dev_mode, required):
    settings = ApplicationSettings(BACKEND_ENV=backend_env, DEV_MODE=dev_mode)
    assert runtime_role_check_required(settings) is required

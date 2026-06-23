"""Unit tests for alembic/utils/idempotency.py.

Each helper executes a single catalog query and returns True/False.  Tests
mock the connection so no database is required.
"""

from unittest.mock import MagicMock

import pytest

from rhesis.backend.alembic.utils.idempotency import (
    column_exists,
    fk_exists,
    index_exists,
    table_exists,
)


def _conn(*, found: bool) -> MagicMock:
    """Return a mock connection whose execute().fetchone() returns a row or None."""
    row = MagicMock() if found else None
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = row
    return conn


class TestColumnExists:
    def test_returns_true_when_column_found(self):
        assert column_exists(_conn(found=True), "user", "email") is True

    def test_returns_false_when_column_absent(self):
        assert column_exists(_conn(found=False), "user", "is_superuser") is False

    def test_passes_table_and_column_as_bind_params(self):
        conn = _conn(found=True)
        column_exists(conn, "token", "scopes")
        _, kwargs = conn.execute.call_args
        params = conn.execute.call_args[0][1]
        assert params["t"] == "token"
        assert params["c"] == "scopes"


class TestTableExists:
    def test_returns_true_when_table_found(self):
        assert table_exists(_conn(found=True), "role") is True

    def test_returns_false_when_table_absent(self):
        assert table_exists(_conn(found=False), "role") is False

    def test_passes_table_as_bind_param(self):
        conn = _conn(found=True)
        table_exists(conn, "permission")
        params = conn.execute.call_args[0][1]
        assert params["t"] == "permission"


class TestIndexExists:
    def test_returns_true_when_index_found(self):
        assert index_exists(_conn(found=True), "ix_role_id") is True

    def test_returns_false_when_index_absent(self):
        assert index_exists(_conn(found=False), "ix_role_id") is False

    def test_passes_index_name_as_bind_param(self):
        conn = _conn(found=True)
        index_exists(conn, "ix_project_membership_role_id")
        params = conn.execute.call_args[0][1]
        assert params["n"] == "ix_project_membership_role_id"


class TestFkExists:
    def test_returns_true_when_constraint_found(self):
        assert fk_exists(_conn(found=True), "project_membership_role_id_fkey", "project_membership") is True

    def test_returns_false_when_constraint_absent(self):
        assert fk_exists(_conn(found=False), "project_membership_role_id_fkey", "project_membership") is False

    def test_passes_constraint_name_and_table_as_bind_params(self):
        conn = _conn(found=True)
        fk_exists(conn, "project_membership_role_id_fkey", "project_membership")
        params = conn.execute.call_args[0][1]
        assert params["n"] == "project_membership_role_id_fkey"
        assert params["t"] == "project_membership"

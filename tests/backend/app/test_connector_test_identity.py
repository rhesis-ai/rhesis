"""Tests for the RHESIS_TEST_ORGANIZATION_ID/RHESIS_TEST_USER_ID startup guard.

See ``app/utils/observability.py:_build_test_identity_override`` for why this
override exists: it lets this backend run its own connector-invoked
endpoints (currently just the architect) under a local identity when the
process is connected to a remote Rhesis instance as a test endpoint.
"""

import uuid

import pytest

from rhesis.backend.app.main import _validate_test_identity_override


def test_noop_when_env_vars_unset(test_db, monkeypatch):
    monkeypatch.delenv("RHESIS_TEST_ORGANIZATION_ID", raising=False)
    monkeypatch.delenv("RHESIS_TEST_USER_ID", raising=False)

    _validate_test_identity_override(test_db)


def test_passes_for_existing_local_org_and_user(
    test_db, test_org_id, authenticated_user_id, monkeypatch
):
    monkeypatch.setenv("RHESIS_TEST_ORGANIZATION_ID", test_org_id)
    monkeypatch.setenv("RHESIS_TEST_USER_ID", authenticated_user_id)

    _validate_test_identity_override(test_db)


def test_raises_for_unknown_organization_id(test_db, authenticated_user_id, monkeypatch):
    monkeypatch.setenv("RHESIS_TEST_ORGANIZATION_ID", str(uuid.uuid4()))
    monkeypatch.setenv("RHESIS_TEST_USER_ID", authenticated_user_id)

    with pytest.raises(RuntimeError, match="RHESIS_TEST_ORGANIZATION_ID"):
        _validate_test_identity_override(test_db)


def test_raises_for_unknown_user_id(test_db, test_org_id, monkeypatch):
    monkeypatch.setenv("RHESIS_TEST_ORGANIZATION_ID", test_org_id)
    monkeypatch.setenv("RHESIS_TEST_USER_ID", str(uuid.uuid4()))

    with pytest.raises(RuntimeError, match="RHESIS_TEST_USER_ID"):
        _validate_test_identity_override(test_db)

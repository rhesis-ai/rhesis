"""Tests for slug resolution in SSO router and auth providers endpoint.

These tests mock the database layer so they run without Postgres.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

# ---------------------------------------------------------------------------
# _get_org_or_404
# ---------------------------------------------------------------------------


def _make_org(org_id=None, slug=None, sso_config=None):
    return SimpleNamespace(
        id=org_id or uuid4(),
        slug=slug,
        sso_config=sso_config,
    )


class _FakeQuery:
    """Chainable mock that returns a pre-set result from .first()."""

    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


def _make_mock_request(host: str = "localhost", port: int = 8080) -> MagicMock:
    """Minimal Starlette Request stand-in for direct get_providers() calls."""
    request = MagicMock()
    request.url = MagicMock()
    request.url.hostname = host
    request.headers = Headers({"host": f"{host}:{port}"})
    return request


class TestGetOrgOr404:
    def _import_func(self):
        from rhesis.backend.ee.sso.router import _get_org_or_404

        return _get_org_or_404

    def test_uuid_lookup(self):
        fn = self._import_func()
        org_id = str(uuid4())
        org = _make_org(org_id=org_id)
        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        result = fn(db, org_id)
        assert result is org

    def test_slug_lookup(self):
        fn = self._import_func()
        org = _make_org(slug="acme-corp")
        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        result = fn(db, "acme-corp")
        assert result is org

    def test_slug_case_insensitive(self):
        fn = self._import_func()
        org = _make_org(slug="acme-corp")
        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        result = fn(db, "ACME-CORP")
        assert result is org

    def test_uuid_not_found_raises_404(self):
        fn = self._import_func()
        db = MagicMock()
        db.query.return_value = _FakeQuery(None)

        with pytest.raises(HTTPException) as exc_info:
            fn(db, str(uuid4()))
        assert exc_info.value.status_code == 404

    def test_slug_not_found_raises_404(self):
        fn = self._import_func()
        db = MagicMock()
        db.query.return_value = _FakeQuery(None)

        with pytest.raises(HTTPException) as exc_info:
            fn(db, "nonexistent-slug")
        assert exc_info.value.status_code == 404

    def test_404_message_is_generic(self):
        """Uniform error message prevents enumeration."""
        fn = self._import_func()
        db = MagicMock()
        db.query.return_value = _FakeQuery(None)

        with pytest.raises(HTTPException) as exc_info:
            fn(db, "nonexistent")
        assert "SSO is not available" in exc_info.value.detail


# ---------------------------------------------------------------------------
# /auth/providers with org param - slug vs UUID resolution
#
# Core's get_providers delegates SSO decoration to the EE provider
# enricher registered by ee.bootstrap; the SSO entry's login_url is
# therefore driven by org.slug from inside EE without core importing
# from rhesis.backend.ee.
# ---------------------------------------------------------------------------


class TestAuthProvidersOrgParam:
    """End-to-end test of the org resolution + enricher pipeline."""

    def test_providers_with_uuid(self):
        """When org is a UUID and has a slug, login_url uses the slug."""
        org_id = uuid4()
        org = _make_org(org_id=org_id, slug="acme-corp", sso_config={"enabled": True})

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        import asyncio

        from rhesis.backend.app.routers.auth import get_providers

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(request=_make_mock_request(), org=str(org_id), db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == "/auth/sso/acme-corp"

    def test_providers_with_slug(self):
        """When org is a slug string, it still resolves correctly."""
        org = _make_org(slug="acme-corp", sso_config={"enabled": True})

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        import asyncio

        from rhesis.backend.app.routers.auth import get_providers

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(request=_make_mock_request(), org="acme-corp", db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == "/auth/sso/acme-corp"

    def test_providers_login_url_falls_back_to_id(self):
        """When org has no slug, login_url uses the org UUID."""
        org_id = uuid4()
        org = _make_org(org_id=org_id, slug=None, sso_config={"enabled": True})

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        import asyncio

        from rhesis.backend.app.routers.auth import get_providers

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(request=_make_mock_request(), org=str(org_id), db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == f"/auth/sso/{org_id}"

    def test_providers_without_org_has_no_sso(self):
        """When no org param, SSO should never appear."""
        db = MagicMock()

        import asyncio

        from rhesis.backend.app.routers.auth import get_providers

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(request=_make_mock_request(), org=None, db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 0

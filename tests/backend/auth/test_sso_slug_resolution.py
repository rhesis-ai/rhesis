"""Tests for slug resolution in SSO router and auth providers endpoint.

These tests mock the database layer so they run without Postgres.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


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


class TestGetOrgOr404:

    def _import_func(self):
        from rhesis.backend.app.routers.sso import _get_org_or_404
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
# ---------------------------------------------------------------------------

class TestAuthProvidersOrgParam:
    """Test the org resolution logic inside get_providers."""

    @patch("rhesis.backend.app.routers.sso.check_sso_available", return_value=True)
    @patch("rhesis.backend.app.routers.sso._get_sso_config")
    def test_providers_with_uuid(self, mock_get_config, mock_check):
        """When org is a UUID, the provider list includes SSO with login_url."""
        from rhesis.backend.app.schemas.sso_config import SSOConfig
        from pydantic import SecretStr

        org_id = uuid4()
        org = _make_org(org_id=org_id, slug="acme-corp", sso_config={})
        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="test",
            client_secret=SecretStr("secret"),
            enabled=True,
        )
        mock_get_config.return_value = config

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        from rhesis.backend.app.routers.auth import get_providers
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(org=str(org_id), db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == f"/auth/sso/acme-corp"

    @patch("rhesis.backend.app.routers.sso.check_sso_available", return_value=True)
    @patch("rhesis.backend.app.routers.sso._get_sso_config")
    def test_providers_with_slug(self, mock_get_config, mock_check):
        """When org is a slug string, it still resolves correctly."""
        from rhesis.backend.app.schemas.sso_config import SSOConfig
        from pydantic import SecretStr

        org = _make_org(slug="acme-corp", sso_config={})
        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="test",
            client_secret=SecretStr("secret"),
            enabled=True,
        )
        mock_get_config.return_value = config

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        from rhesis.backend.app.routers.auth import get_providers
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(org="acme-corp", db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == "/auth/sso/acme-corp"

    @patch("rhesis.backend.app.routers.sso.check_sso_available", return_value=True)
    @patch("rhesis.backend.app.routers.sso._get_sso_config")
    def test_providers_login_url_falls_back_to_id(self, mock_get_config, mock_check):
        """When org has no slug, login_url uses the org UUID."""
        from rhesis.backend.app.schemas.sso_config import SSOConfig
        from pydantic import SecretStr

        org_id = uuid4()
        org = _make_org(org_id=org_id, slug=None, sso_config={})
        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="test",
            client_secret=SecretStr("secret"),
            enabled=True,
        )
        mock_get_config.return_value = config

        db = MagicMock()
        db.query.return_value = _FakeQuery(org)

        from rhesis.backend.app.routers.auth import get_providers
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(org=str(org_id), db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 1
        assert sso_providers[0].login_url == f"/auth/sso/{org_id}"

    def test_providers_without_org_has_no_sso(self):
        """When no org param, SSO should never appear."""
        db = MagicMock()

        from rhesis.backend.app.routers.auth import get_providers
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            get_providers(org=None, db=db)
        )

        sso_providers = [p for p in result.providers if p.name == "sso"]
        assert len(sso_providers) == 0

"""Tests for SSO router helpers and endpoint logic.

Pure unit tests that mock DB and encryption -- no network or Postgres needed.
"""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from rhesis.backend.app.config.settings import get_application_settings


@pytest.fixture(autouse=True)
def clear_application_settings_cache():
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


# ---------------------------------------------------------------------------
# _validate_return_to
# ---------------------------------------------------------------------------


class TestValidateReturnTo:
    def _validate(self, val):
        from rhesis.backend.ee.sso.router import _validate_return_to

        return _validate_return_to(val)

    def test_none_defaults_to_dashboard(self):
        assert self._validate(None) == "/architect"

    def test_empty_defaults_to_dashboard(self):
        assert self._validate("") == "/architect"

    def test_valid_relative_path(self):
        assert self._validate("/settings") == "/settings"

    def test_valid_nested_path(self):
        assert self._validate("/org/settings/sso") == "/org/settings/sso"

    def test_absolute_http_blocked(self):
        assert self._validate("http://evil.com") == "/architect"

    def test_absolute_https_blocked(self):
        assert self._validate("https://evil.com/foo") == "/architect"

    def test_protocol_relative_blocked(self):
        assert self._validate("//evil.com") == "/architect"

    def test_javascript_scheme_blocked(self):
        assert self._validate("javascript:alert(1)") == "/architect"

    def test_data_scheme_blocked(self):
        assert self._validate("data:text/html,<h1>x</h1>") == "/architect"

    def test_backslash_blocked(self):
        assert self._validate("\\\\evil.com") == "/architect"

    def test_encoded_double_slash_blocked(self):
        assert self._validate("/%2f/evil.com") == "/architect"

    def test_double_encoded_blocked(self):
        assert self._validate("/%252f%252fevil.com") == "/architect"


# ---------------------------------------------------------------------------
# _generate_pkce
# ---------------------------------------------------------------------------


class TestGeneratePkce:
    def test_returns_verifier_and_challenge(self):
        from rhesis.backend.ee.sso.router import _generate_pkce

        verifier, challenge = _generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 40
        assert len(challenge) > 20

    def test_each_call_unique(self):
        from rhesis.backend.ee.sso.router import _generate_pkce

        a = _generate_pkce()
        b = _generate_pkce()
        assert a[0] != b[0]
        assert a[1] != b[1]


# ---------------------------------------------------------------------------
# check_sso_available
# ---------------------------------------------------------------------------


class TestCheckSSOAvailable:
    def test_available_with_encryption_key(self):
        from rhesis.backend.ee.sso.router import check_sso_available

        assert check_sso_available() is True

    @patch(
        "rhesis.backend.ee.sso.encryption.is_sso_encryption_available",
        return_value=False,
    )
    def test_unavailable_without_encryption(self, _mock):
        from rhesis.backend.ee.sso.router import check_sso_available

        assert check_sso_available() is False


# ---------------------------------------------------------------------------
# SSOConfigRequest with slug
# ---------------------------------------------------------------------------


class TestSSOConfigRequestSlug:
    def test_slug_included(self):
        from rhesis.backend.ee.sso.router import SSOConfigRequest

        req = SSOConfigRequest(
            issuer_url="https://idp.example.com",
            client_id="test",
            slug="acme-corp",
        )
        assert req.slug == "acme-corp"

    def test_slug_defaults_to_none(self):
        from rhesis.backend.ee.sso.router import SSOConfigRequest

        req = SSOConfigRequest(
            issuer_url="https://idp.example.com",
            client_id="test",
        )
        assert req.slug is None


# ---------------------------------------------------------------------------
# _get_sso_config - decryption and parsing
# ---------------------------------------------------------------------------


class TestGetSSOConfig:
    def test_no_config_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(id=uuid4(), sso_config=None)
        assert _get_sso_config(org) is None

    def test_empty_dict_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(id=uuid4(), sso_config={})
        assert _get_sso_config(org) is None

    def test_valid_config_with_encrypted_secret(self):
        from rhesis.backend.ee.sso.encryption import sso_encrypt
        from rhesis.backend.ee.sso.router import _get_sso_config

        encrypted = sso_encrypt("my-secret")
        org = SimpleNamespace(
            id=uuid4(),
            sso_config={
                "enabled": True,
                "provider_type": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "my-client",
                "client_secret": encrypted,
                "scopes": "openid email profile",
                "auto_provision_users": False,
                "allowed_domains": None,
                "allowed_auth_methods": None,
            },
        )
        config = _get_sso_config(org)
        assert config is not None
        assert config.client_id == "my-client"
        assert config.get_secret_value() == "my-secret"

    def test_plaintext_secret_fallback_in_dev(self, monkeypatch):
        from rhesis.backend.ee.sso.router import _get_sso_config

        monkeypatch.setenv("BACKEND_ENV", "development")
        get_application_settings.cache_clear()

        org = SimpleNamespace(
            id=uuid4(),
            sso_config={
                "enabled": True,
                "provider_type": "oidc",
                "issuer_url": "http://localhost:8180/realms/dev",
                "client_id": "dev-client",
                "client_secret": "plain-text-secret",
                "scopes": "openid email profile",
                "auto_provision_users": False,
            },
        )
        config = _get_sso_config(org)
        assert config is not None
        assert config.get_secret_value() == "plain-text-secret"

    def test_corrupt_config_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(
            id=uuid4(),
            sso_config={"issuer_url": "not-valid", "client_id": "x"},
        )
        assert _get_sso_config(org) is None


# ---------------------------------------------------------------------------
# sso_callback -- tenant GUC setup
# ---------------------------------------------------------------------------


class TestSSOCallbackTenantContext:
    """The callback must set the RLS GUCs before provisioning a user.

    The route runs on ``get_db_session``, which sets no tenant GUCs (the user's
    identity is unknown until the IdP responds).  Auto-provisioning a new user
    writes RLS-protected tenant tables via the org-membership hook, and those
    policies read ``app.current_organization``.  Without the GUCs, a first-time
    SSO login dies with ``unrecognized configuration parameter
    "app.current_organization"``.  Same contract every other
    ``on_user_org_assigned`` caller follows (``routers/organization.py``,
    ``local_init.py``).
    """

    ORG_SLUG = "netgo"

    @pytest.fixture
    def callback_env(self, monkeypatch):
        """Patch out everything the callback touches, recording call order."""
        from rhesis.backend.app.utils.rate_limit import limiter
        from rhesis.backend.ee.sso import router as sso_router

        # The route is rate limited; the decorator short-circuits on `enabled`
        # so the coroutine can be awaited directly.
        monkeypatch.setattr(limiter, "enabled", False)

        org = SimpleNamespace(id=uuid4())
        user = SimpleNamespace(id=uuid4())
        auth_user = SimpleNamespace(email="new.user@netgo.example")
        calls = []

        def _record(name, retval=None):
            def _fn(*args, **kwargs):
                calls.append((name, args, kwargs))
                return retval

            return _fn

        async def _authenticate(*args, **kwargs):
            return auth_user

        monkeypatch.setattr(
            sso_router,
            "verify_signed_state",
            lambda _s: {"org_id": self.ORG_SLUG, "nonce": "n", "return_to": "/architect"},
        )
        monkeypatch.setattr(sso_router, "check_sso_available", lambda: True)
        monkeypatch.setattr(sso_router, "_get_org_or_404", lambda _db, _slug: org)
        monkeypatch.setattr(
            sso_router, "_get_sso_config", lambda _org: SimpleNamespace(enabled=True)
        )
        monkeypatch.setattr(
            sso_router, "_get_sso_callback_url", lambda: "https://api.example/auth/sso/callback"
        )
        monkeypatch.setattr(
            sso_router,
            "OIDCProvider",
            lambda _cfg: SimpleNamespace(authenticate=_authenticate),
        )

        # raising=False so that removing the call (or its import) surfaces as the
        # assertion below rather than an AttributeError in this fixture.
        monkeypatch.setattr(
            sso_router,
            "set_session_variables",
            _record("set_session_variables"),
            raising=False,
        )
        monkeypatch.setattr(
            sso_router, "find_or_create_sso_user", _record("find_or_create_sso_user", user)
        )

        monkeypatch.setattr(sso_router, "audit_log", _record("audit_log"))
        monkeypatch.setattr(sso_router, "clear_user_logout", _record("clear_user_logout"))
        monkeypatch.setattr(
            sso_router, "create_session_token", _record("create_session_token", "sess")
        )
        monkeypatch.setattr(
            sso_router, "create_refresh_token", _record("create_refresh_token", "refresh")
        )
        monkeypatch.setattr(sso_router, "regenerate_session", _record("regenerate_session"))

        async def _build_redirect_url(*args, **kwargs):
            calls.append(("build_redirect_url", args, kwargs))
            return "https://app.example/auth/signin?code=abc"

        monkeypatch.setattr(sso_router, "build_redirect_url", _build_redirect_url)

        request = SimpleNamespace(
            session={"sso_code_verifier": "verifier", "sso_org_id": self.ORG_SLUG},
        )
        db = SimpleNamespace(commit=lambda: calls.append(("commit", (), {})))

        return SimpleNamespace(
            org=org,
            user=user,
            calls=calls,
            request=request,
            db=db,
            names=lambda: [c[0] for c in calls],
        )

    async def _run(self, env):
        from rhesis.backend.ee.sso.router import sso_callback

        return await sso_callback(
            request=env.request, code="authcode", state="signedstate", db=env.db
        )

    @pytest.mark.asyncio
    async def test_guc_set_before_user_provisioning(self, callback_env):
        await self._run(callback_env)

        names = callback_env.names()
        assert "set_session_variables" in names, (
            "callback never set the tenant GUCs; first-time SSO login will fail "
            "with 'unrecognized configuration parameter'"
        )
        assert names.index("set_session_variables") < names.index("find_or_create_sso_user"), (
            "GUCs must be set before provisioning, which writes RLS-protected tables"
        )

    @pytest.mark.asyncio
    async def test_guc_uses_resolved_org_uuid_not_slug(self, callback_env):
        await self._run(callback_env)

        matches = [c for c in callback_env.calls if c[0] == "set_session_variables"]
        assert matches, "callback never set the tenant GUCs"
        _name, args, _kwargs = matches[0]

        assert args[0] is callback_env.db
        # The org UUID, not the slug from the signed state -- RLS compares
        # organization_id against this value.
        assert args[1] == str(callback_env.org.id)
        assert args[1] != self.ORG_SLUG

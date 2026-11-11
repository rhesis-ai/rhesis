"""SSO ``return_to`` and the checks relaxed for local development.

``return_to`` must be a same-origin path by the same rule as the core login. The
relaxed issuer and secret checks apply only to local/development, not staging, and
"localhost" means the loopback host, not any URL containing the word.
"""

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from rhesis.backend.app.config.settings import get_application_settings

DEFAULT = "/architect"

UNSAFE = [
    "//evil.example",
    "/\\evil.example",
    "/%5Cevil.example",
    "/\t/evil.example",
    "/%09/evil.example",
    "/%0A/evil.example",
    "/%252F%252Fevil.example",
    "javascript:alert(1)",
    "https://evil.example",
    "evil.example",
]

SAFE = ["/", "/architect", "/tests/123?tab=runs#top", "/projects/a:b"]


@pytest.fixture
def backend_env(monkeypatch):
    def _set(value: str):
        monkeypatch.setenv("BACKEND_ENV", value)
        get_application_settings.cache_clear()

    yield _set
    get_application_settings.cache_clear()


def _config(issuer_url: str):
    from rhesis.backend.ee.sso.schemas import SSOConfig

    return SSOConfig(
        issuer_url=issuer_url, client_id="my-client", client_secret=SecretStr("my-secret")
    )


@pytest.mark.unit
@pytest.mark.parametrize("value", UNSAFE)
def test_return_to_rejects_off_origin_targets(value):
    from rhesis.backend.ee.sso.router import _validate_return_to

    assert _validate_return_to(value) == DEFAULT


@pytest.mark.unit
@pytest.mark.parametrize("value", SAFE)
def test_return_to_keeps_same_origin_paths(value):
    from rhesis.backend.ee.sso.router import _validate_return_to

    assert _validate_return_to(value) == value


@pytest.mark.unit
class TestIssuerDevRelaxations:
    def test_http_requires_a_loopback_host(self, backend_env):
        backend_env("local")
        with pytest.raises(ValueError, match="HTTPS"):
            _config("http://localhost.evil.example/realms/test")
        with pytest.raises(ValueError, match="HTTPS"):
            _config("http://evil.example/localhost")

    def test_http_localhost_rejected_in_staging(self, backend_env):
        backend_env("staging")
        with pytest.raises(ValueError, match="HTTPS"):
            _config("http://localhost:8080/realms/test")

    def test_non_443_port_rejected_in_staging(self, backend_env):
        backend_env("staging")
        with pytest.raises(ValueError, match="port 443"):
            _config("https://idp.example.com:8443/realms/test")

    def test_local_development_keeps_its_relaxations(self, backend_env):
        backend_env("development")
        assert _config("http://localhost:8080/realms/test")
        assert _config("https://idp.example.com:8443/realms/test")


@pytest.mark.unit
class TestClientSecretFallback:
    def _org(self):
        return SimpleNamespace(
            id="org-1",
            sso_config={
                "issuer_url": "https://idp.example.com",
                "client_id": "my-client",
                "client_secret": "not-encrypted",
            },
        )

    def test_undecryptable_secret_is_unusable_in_staging(self, backend_env):
        from rhesis.backend.ee.sso.router import _get_sso_config

        backend_env("staging")
        assert _get_sso_config(self._org()) is None

    def test_undecryptable_secret_falls_back_in_local(self, backend_env):
        from rhesis.backend.ee.sso.router import _get_sso_config

        backend_env("local")
        config = _get_sso_config(self._org())
        assert config is not None
        assert config.client_secret.get_secret_value() == "not-encrypted"

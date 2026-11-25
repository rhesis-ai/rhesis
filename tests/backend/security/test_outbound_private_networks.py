"""Staging and production do not reach private/loopback targets by default.

The localhost/private-network bypass (and the TLS-verification skip for a local
IdP) is a local/self-host convenience. On the hosted platform it must stay off:
staging and production block loopback, private and cloud-metadata targets unless
a self-host operator explicitly opts in with ``OUTBOUND_ALLOW_PRIVATE_NETWORKS``
(issue #3188). The hosted platform leaves that override unset.
"""

import pytest

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.utils import ssrf_http_client


@pytest.fixture
def reset_settings_cache():
    """Rebuild the cached settings around a test so env changes take effect."""
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


def _set_env(monkeypatch, backend_env: str, override: str | None) -> None:
    monkeypatch.setenv("BACKEND_ENV", backend_env)
    if override is None:
        monkeypatch.delenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", raising=False)
    else:
        monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", override)
    get_application_settings.cache_clear()


@pytest.mark.unit
@pytest.mark.parametrize("backend_env", ["production", "staging"])
def test_hosted_envs_block_loopback_by_default(monkeypatch, reset_settings_cache, backend_env):
    """With no override, staging and production reject loopback and private URLs."""
    _set_env(monkeypatch, backend_env, None)

    assert ssrf_http_client.private_targets_allowed() is False
    for url in ("http://127.0.0.1/", "http://localhost/", "https://[::1]/"):
        with pytest.raises(ssrf_http_client.SSRFError):
            ssrf_http_client.validate_outbound_url(url)


@pytest.mark.unit
@pytest.mark.parametrize("backend_env", ["production", "staging"])
def test_hosted_envs_do_not_skip_tls_for_localhost(monkeypatch, reset_settings_cache, backend_env):
    """The TLS-verification skip for a local IdP never applies on the hosted platform."""
    _set_env(monkeypatch, backend_env, None)

    assert ssrf_http_client._localhost_allowed("localhost") is False
    assert ssrf_http_client._localhost_allowed("127.0.0.1") is False


@pytest.mark.unit
def test_self_host_override_reaches_loopback(monkeypatch, reset_settings_cache):
    """A self-host operator may opt in, even in production (issue #3188)."""
    _set_env(monkeypatch, "production", "true")

    assert ssrf_http_client.private_targets_allowed() is True
    # Does not raise: loopback is allowed once the operator opts in.
    ssrf_http_client.validate_outbound_url("http://127.0.0.1/")


@pytest.mark.unit
def test_metadata_stays_blocked_even_with_override(monkeypatch, reset_settings_cache):
    """Cloud-metadata addresses are blocked regardless of the override."""
    _set_env(monkeypatch, "production", "true")

    with pytest.raises(ssrf_http_client.SSRFError):
        ssrf_http_client.validate_outbound_url("http://169.254.169.254/")

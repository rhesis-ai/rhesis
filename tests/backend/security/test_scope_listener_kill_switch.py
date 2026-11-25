"""The scope-listener kill switch must never take effect in production.

``RHESIS_DISABLE_SCOPE_LISTENER=1`` turns off the ORM-layer tenant filter and
stamp. It is a local/self-host escape hatch; in production it is ignored, so a
misconfigured environment variable cannot silently drop tenant scoping on a
hosted deployment.
"""

import pytest

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.models import scope_events


@pytest.fixture
def reset_settings_cache():
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


def _set_env(monkeypatch, backend_env: str) -> None:
    monkeypatch.setenv("BACKEND_ENV", backend_env)
    monkeypatch.setenv("RHESIS_DISABLE_SCOPE_LISTENER", "1")
    get_application_settings.cache_clear()


@pytest.mark.unit
def test_kill_switch_ignored_in_production(monkeypatch, reset_settings_cache):
    _set_env(monkeypatch, "production")

    assert scope_events._kill_switch_set() is True
    assert scope_events._kill_switch_active() is False


@pytest.mark.unit
@pytest.mark.parametrize("backend_env", ["local", "development", "staging"])
def test_kill_switch_honoured_outside_production(monkeypatch, reset_settings_cache, backend_env):
    _set_env(monkeypatch, backend_env)

    assert scope_events._kill_switch_active() is True


@pytest.mark.unit
def test_kill_switch_inactive_when_unset(monkeypatch, reset_settings_cache):
    monkeypatch.setenv("BACKEND_ENV", "local")
    monkeypatch.delenv("RHESIS_DISABLE_SCOPE_LISTENER", raising=False)
    get_application_settings.cache_clear()

    assert scope_events._kill_switch_active() is False

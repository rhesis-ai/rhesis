"""Unit tests for the Parameters cache."""

from __future__ import annotations

import time

from rhesis.sdk.parameters._cache import ParameterCache


def test_cache_miss_returns_none():
    c = ParameterCache()
    assert c.get("proj") is None


def test_cache_hit_returns_value():
    c = ParameterCache()
    c.put("proj", "resolved", environment="default")
    assert c.get("proj", environment="default") == "resolved"


def test_cache_version_pin_never_expires():
    c = ParameterCache(ttl=0.01)
    c.put("proj", "pinned", version="v_abc")
    time.sleep(0.02)
    assert c.get("proj", version="v_abc") == "pinned"


def test_cache_environment_expires_after_ttl():
    c = ParameterCache(ttl=0.01)
    c.put("proj", "resolved", environment="default")
    time.sleep(0.02)
    assert c.get("proj", environment="default") is None


def test_cache_invalidate_project():
    c = ParameterCache()
    c.put("proj1", "a", environment="default")
    c.put("proj2", "b", environment="default")
    c.invalidate("proj1")
    assert c.get("proj1", environment="default") is None
    assert c.get("proj2", environment="default") == "b"


def test_cache_invalidate_all():
    c = ParameterCache()
    c.put("proj1", "a", environment="default")
    c.put("proj2", "b", environment="default")
    c.invalidate()
    assert c.get("proj1", environment="default") is None
    assert c.get("proj2", environment="default") is None


def test_cache_key_isolation():
    c = ParameterCache()
    c.put("proj", "by_environment", environment="default")
    c.put("proj", "by_version", version="v_x")
    c.put("proj", "by_exp", experiment_id="e1")

    assert c.get("proj", environment="default") == "by_environment"
    assert c.get("proj", version="v_x") == "by_version"
    assert c.get("proj", experiment_id="e1") == "by_exp"
    assert c.get("proj") is None  # no params = different key

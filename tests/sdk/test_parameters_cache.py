"""Unit tests for the Parameters cache."""

from __future__ import annotations

import time

from rhesis.sdk.parameters._cache import ParameterCache


def test_cache_miss_returns_none():
    c = ParameterCache()
    assert c.get("proj") is None


def test_cache_hit_returns_value():
    c = ParameterCache()
    c.put("proj", "resolved", label="default")
    assert c.get("proj", label="default") == "resolved"


def test_cache_version_pin_never_expires():
    c = ParameterCache(ttl=0.01)
    c.put("proj", "pinned", version="v_abc")
    time.sleep(0.02)
    assert c.get("proj", version="v_abc") == "pinned"


def test_cache_label_expires_after_ttl():
    c = ParameterCache(ttl=0.01)
    c.put("proj", "resolved", label="default")
    time.sleep(0.02)
    assert c.get("proj", label="default") is None


def test_cache_invalidate_project():
    c = ParameterCache()
    c.put("proj1", "a", label="default")
    c.put("proj2", "b", label="default")
    c.invalidate("proj1")
    assert c.get("proj1", label="default") is None
    assert c.get("proj2", label="default") == "b"


def test_cache_invalidate_all():
    c = ParameterCache()
    c.put("proj1", "a", label="default")
    c.put("proj2", "b", label="default")
    c.invalidate()
    assert c.get("proj1", label="default") is None
    assert c.get("proj2", label="default") is None


def test_cache_key_isolation():
    c = ParameterCache()
    c.put("proj", "by_label", label="default")
    c.put("proj", "by_version", version="v_x")
    c.put("proj", "by_exp", experiment_id="e1")

    assert c.get("proj", label="default") == "by_label"
    assert c.get("proj", version="v_x") == "by_version"
    assert c.get("proj", experiment_id="e1") == "by_exp"
    assert c.get("proj") is None  # no params = different key

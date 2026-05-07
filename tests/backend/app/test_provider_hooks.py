"""Unit tests for :mod:`rhesis.backend.app.auth.provider_hooks`."""

from __future__ import annotations

from rhesis.backend.app.auth import provider_hooks


def setup_function():
    provider_hooks.reset_enrichers()


def teardown_function():
    provider_hooks.reset_enrichers()


def test_apply_enrichers_with_no_callbacks_is_identity():
    initial = [{"name": "google"}]
    result = provider_hooks.apply_enrichers(initial, org=None)
    assert result == initial


def test_register_then_apply_runs_callback():
    def add_sso(providers, org):
        return [*providers, {"name": "sso"}]

    provider_hooks.register_provider_enricher(add_sso)
    result = provider_hooks.apply_enrichers([{"name": "google"}], org=None)
    assert [p["name"] for p in result] == ["google", "sso"]


def test_register_is_idempotent():
    def cb(providers, org):
        return [*providers, {"name": "sso"}]

    provider_hooks.register_provider_enricher(cb)
    provider_hooks.register_provider_enricher(cb)
    result = provider_hooks.apply_enrichers([], org=None)
    # Same callback registered twice should still execute once.
    assert len(result) == 1


def test_enrichers_chain_in_registration_order():
    """Each callback sees the output of the previous one."""

    def add_a(providers, org):
        return [*providers, {"name": "a"}]

    def add_b(providers, org):
        return [*providers, {"name": "b"}]

    provider_hooks.register_provider_enricher(add_a)
    provider_hooks.register_provider_enricher(add_b)
    result = provider_hooks.apply_enrichers([], org=None)
    assert [p["name"] for p in result] == ["a", "b"]


def test_enricher_can_filter_existing_providers():
    """Used by the SSO enricher's ``allowed_auth_methods`` behaviour."""

    def keep_only_google(providers, org):
        return [p for p in providers if p["name"] == "google"]

    provider_hooks.register_provider_enricher(keep_only_google)
    result = provider_hooks.apply_enrichers(
        [{"name": "google"}, {"name": "azure"}], org=None
    )
    assert [p["name"] for p in result] == ["google"]


def test_reset_enrichers_clears_registry():
    provider_hooks.register_provider_enricher(lambda providers, org: providers)
    provider_hooks.reset_enrichers()
    assert provider_hooks.apply_enrichers([{"name": "google"}], org=None) == [
        {"name": "google"}
    ]

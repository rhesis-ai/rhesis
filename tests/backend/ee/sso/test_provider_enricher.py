"""Unit tests for :func:`rhesis.backend.ee.sso.provider_enricher.sso_provider_enricher`.

These tests focus on the enricher's branching logic in isolation: with
no organisation, with an unavailable feature, with disabled SSO, with
enabled SSO and slug, with the UUID fallback, and with an
``allowed_auth_methods`` filter.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from rhesis.backend.ee.sso.provider_enricher import sso_provider_enricher


def _org(org_id=None, slug=None, sso_config=None):
    return SimpleNamespace(
        id=org_id or uuid4(),
        slug=slug,
        sso_config=sso_config,
    )


def test_enricher_no_org_returns_unchanged():
    initial = [{"name": "google"}]
    assert sso_provider_enricher(initial, org=None) is initial


def test_enricher_returns_unchanged_when_feature_unavailable():
    initial = [{"name": "google"}]
    org = _org(slug="acme", sso_config={"enabled": True})
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=False,
    ):
        assert sso_provider_enricher(initial, org) is initial


def test_enricher_returns_unchanged_when_sso_disabled():
    initial = [{"name": "google"}]
    org = _org(slug="acme", sso_config={"enabled": False})
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=True,
    ):
        assert sso_provider_enricher(initial, org) is initial


def test_enricher_uses_slug_in_login_url():
    org = _org(slug="acme-corp", sso_config={"enabled": True})
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=True,
    ):
        result = sso_provider_enricher([{"name": "google"}], org)
    sso_entries = [p for p in result if p["name"] == "sso"]
    assert len(sso_entries) == 1
    assert sso_entries[0]["login_url"] == "/auth/sso/acme-corp"


def test_enricher_falls_back_to_uuid_when_no_slug():
    org_id = uuid4()
    org = _org(org_id=org_id, slug=None, sso_config={"enabled": True})
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=True,
    ):
        result = sso_provider_enricher([], org)
    assert result[0]["login_url"] == f"/auth/sso/{org_id}"


def test_enricher_allowed_auth_methods_filters_other_providers():
    org = _org(
        slug="acme",
        sso_config={"enabled": True, "allowed_auth_methods": ["sso"]},
    )
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=True,
    ):
        result = sso_provider_enricher(
            [{"name": "google"}, {"name": "azure"}], org
        )
    # Only sso should remain after filtering.
    assert [p["name"] for p in result] == ["sso"]


def test_enricher_allowed_auth_methods_keeps_listed_providers():
    org = _org(
        slug="acme",
        sso_config={"enabled": True, "allowed_auth_methods": ["sso", "google"]},
    )
    with patch(
        "rhesis.backend.ee.sso.provider_enricher.FeatureRegistry.is_available",
        return_value=True,
    ):
        result = sso_provider_enricher(
            [{"name": "google"}, {"name": "azure"}], org
        )
    assert sorted(p["name"] for p in result) == ["google", "sso"]

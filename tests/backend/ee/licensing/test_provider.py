"""Unit tests for :class:`~rhesis.backend.ee.licensing.provider.SignedTokenLicenseProvider`."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)

_ORG_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ORG_ID = UUID(_ORG_UUID)

_SSO_FEATURE = Feature(name=FeatureName.SSO, display_name="SSO")


def _make_org(org_id: str = _ORG_UUID, license_token: str | None = None) -> MagicMock:
    org = MagicMock()
    org.id = UUID(org_id)
    org.license = license_token
    return org


@pytest.fixture
def provider():
    return SignedTokenLicenseProvider()


@pytest.fixture
def clean_registry():
    FeatureRegistry.reset()
    yield
    FeatureRegistry.reset()


class TestValidLicense:
    def test_env_blanket_token_allows_feature(self, provider, mint_token):
        token = mint_token(sub="*")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is True

    def test_org_column_token_allows_feature(self, provider, mint_token):
        token = mint_token(sub=_ORG_UUID)
        org = _make_org(license_token=token)
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            assert provider.allows_feature(_SSO_FEATURE, org) is True

    def test_org_column_sub_mismatch_denies(self, provider, mint_token):
        other_org = "11111111-2222-3333-4444-555555555555"
        token = mint_token(sub=other_org)
        org = _make_org()  # different id
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            assert provider.allows_feature(_SSO_FEATURE, org) is False

    def test_explicit_feature_list_allows_sso(self, provider, mint_token):
        token = mint_token(sub="*", all_features=False, features=["sso"])
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is True

    def test_explicit_feature_list_denies_unlisted(self, provider, mint_token):
        token = mint_token(sub="*", all_features=False, features=["api_clients"])
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is False


class TestExpiredLicense:
    def test_expired_token_denies_feature(self, provider, mint_token):
        past_exp = int(time.time()) - 7200
        token = mint_token(sub="*", exp=past_exp)
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is False

    def test_expired_token_info_shows_unlicensed(self, provider, mint_token):
        past_exp = int(time.time()) - 7200
        token = mint_token(sub="*", exp=past_exp, edition="trial")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            info = provider.info(org=org)
        assert info["licensed"] is False


class TestCanceledLicense:
    def test_canceled_status_denies_feature(self, provider, mint_token):
        token = mint_token(sub="*", status="canceled")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is False

    def test_canceled_status_info_reports_edition_unlicensed(self, provider, mint_token):
        """A present-but-canceled license reports its edition with licensed=False,
        and is consistent with allows_feature denying access (shared is_active gate).
        """
        token = mint_token(sub="*", status="canceled", edition="enterprise")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            info = provider.info(org=org)
            allowed = provider.allows_feature(_SSO_FEATURE, org)
        assert info == {"edition": "enterprise", "licensed": False}
        assert allowed is False

    def test_past_due_status_is_consistent(self, provider, mint_token):
        """past_due grants access AND reports licensed=True — both sides agree."""
        token = mint_token(sub="*", status="past_due", edition="enterprise")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            info = provider.info(org=org)
            allowed = provider.allows_feature(_SSO_FEATURE, org)
        assert info["licensed"] is True
        assert allowed is True

    def test_unknown_status_is_consistent(self, provider, mint_token):
        """An unknown status denies access AND reports licensed=False (no drift)."""
        token = mint_token(sub="*", status="suspended", edition="enterprise")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            info = provider.info(org=org)
            allowed = provider.allows_feature(_SSO_FEATURE, org)
        assert info["licensed"] is False
        assert allowed is False


class TestPrecedence:
    def test_env_token_takes_precedence_over_org_column(self, provider, mint_token):
        env_token = mint_token(sub="*")
        past_exp = int(time.time()) - 7200
        org_token = mint_token(sub=_ORG_UUID, exp=past_exp)
        org = _make_org(license_token=org_token)
        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is True

    def test_non_star_env_token_falls_through_to_org_column(self, provider, mint_token):
        env_token = mint_token(sub="different-org-id")  # sub != "*"
        org_token = mint_token(sub=_ORG_UUID)
        org = _make_org(license_token=org_token)
        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            assert provider.allows_feature(_SSO_FEATURE, org) is True

    def test_no_token_denies_feature(self, provider):
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            assert provider.allows_feature(_SSO_FEATURE, org) is False


class TestMissingKeys:
    def test_no_keys_denies_feature(self, provider, mint_token):
        from rhesis.backend.ee.licensing.verify import _parse_token

        _parse_token.cache_clear()
        token = mint_token(sub="*")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            with patch("rhesis.backend.ee.licensing.verify.get_public_keys", return_value={}):
                result = provider.allows_feature(_SSO_FEATURE, org)
        _parse_token.cache_clear()
        assert result is False


class TestInfoMethod:
    def test_info_licensed(self, provider, mint_token):
        token = mint_token(sub="*", edition="enterprise")
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
            info = provider.info(org=org)
        assert info["edition"] == "enterprise"
        assert info["licensed"] is True

    def test_info_no_org_returns_community(self, provider):
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            info = provider.info(org=None)
        assert info["edition"] == "community"
        assert info["licensed"] is False

    def test_info_no_valid_token_returns_community(self, provider):
        org = _make_org()
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            info = provider.info(org=org)
        assert info["edition"] == "community"
        assert info["licensed"] is False

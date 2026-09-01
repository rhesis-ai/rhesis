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
        assert info["edition"] == "enterprise"
        assert info["licensed"] is False
        # Still a paid *tier*, just not an active licence. That pair is what
        # lets a client tell this apart from a free org and show it as lapsed
        # rather than as never having paid.
        assert info["is_paid"] is True
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

    def test_inactive_blanket_token_does_not_shadow_an_active_org_licence(
        self, provider, mint_token
    ):
        """The bug: a stale blanket token used to win on ``sub == "*"`` alone.

        No status check meant a canceled ``RHESIS_LICENSE`` was returned ahead
        of the org's own valid licence, so an org was reported unlicensed and
        held to community limits right after being issued a good token -- with
        the blanket token's edition as the only clue anything was wrong.

        An active licence now beats an inactive one regardless of source.
        """
        env_token = mint_token(sub="*", edition="team", status="canceled")
        org_token = mint_token(sub=_ORG_UUID, edition="enterprise")
        org = _make_org(license_token=org_token)

        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            info = provider.info(org=org)
            allowed = provider.allows_feature(_SSO_FEATURE, org)

        assert info["licensed"] is True
        assert info["edition"] == "enterprise"
        assert allowed is True

    def test_warns_once_per_process_not_once_per_request(self, provider, mint_token):
        """The shadowing case sits on the request path, so it must not log per call.

        ``_resolve_entitlements`` is reached from ``allows_feature`` (every
        ``require_feature`` gate), from ``license_info`` (the features and usage
        endpoints) and from ``ConfigQuotaProvider.get_policy`` (every
        ``require_quota`` gate) -- several times per request. A misconfigured
        deployment would otherwise bury the warning it exists to raise.
        """
        from rhesis.backend.ee.licensing.provider import _warn_blanket_inactive

        _warn_blanket_inactive.cache_clear()
        env_token = mint_token(sub="*", edition="team", status="canceled")
        org_token = mint_token(sub=_ORG_UUID, edition="enterprise")
        org = _make_org(license_token=org_token)

        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            with patch("rhesis.backend.ee.licensing.provider.logger.warning") as warn:
                for _ in range(5):
                    provider.allows_feature(_SSO_FEATURE, org)
                    provider.info(org=org)

        assert warn.call_count == 1, f"expected one warning per process, got {warn.call_count}"
        _warn_blanket_inactive.cache_clear()

    def test_a_different_stale_status_is_reported_once_more(self, provider, mint_token):
        """Keyed on status, so canceled -> expired is a new misconfiguration
        worth one more line rather than being swallowed forever."""
        from rhesis.backend.ee.licensing.provider import _warn_blanket_inactive

        _warn_blanket_inactive.cache_clear()
        org_token = mint_token(sub=_ORG_UUID, edition="enterprise")
        org = _make_org(license_token=org_token)

        with patch("rhesis.backend.ee.licensing.provider.logger.warning") as warn:
            for status in ("canceled", "canceled", "unpaid", "unpaid"):
                token = mint_token(sub="*", edition="team", status=status)
                with patch.dict("os.environ", {"RHESIS_LICENSE": token}):
                    provider.allows_feature(_SSO_FEATURE, org)

        assert warn.call_count == 2
        _warn_blanket_inactive.cache_clear()

    def test_active_blanket_token_still_wins_over_an_active_org_licence(self, provider, mint_token):
        """The documented precedence, unchanged: between two *active* licences
        the blanket one still takes priority."""
        env_token = mint_token(sub="*", edition="team")
        org_token = mint_token(sub=_ORG_UUID, edition="enterprise")
        org = _make_org(license_token=org_token)

        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            info = provider.info(org=org)

        assert info["edition"] == "team"
        assert info["licensed"] is True

    def test_reports_the_lapsed_edition_when_nothing_is_active(self, provider, mint_token):
        """With no active licence anywhere, still name the one that expired.

        Returning ``None`` here would report the org as ``community`` and throw
        away the only actionable detail -- which licence lapsed. Nothing is
        granted either way, since callers gate on ``is_active()``.
        """
        env_token = mint_token(sub="*", edition="team", status="canceled")
        org_token = mint_token(sub=_ORG_UUID, edition="enterprise", status="canceled")
        org = _make_org(license_token=org_token)

        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            info = provider.info(org=org)
            allowed = provider.allows_feature(_SSO_FEATURE, org)

        # Blanket first, matching the precedence for active licences.
        assert info["edition"] == "team"
        assert info["licensed"] is False
        assert allowed is False

    def test_inactive_blanket_token_with_no_org_licence_still_names_itself(
        self, provider, mint_token
    ):
        """A single-tenant deployment whose blanket licence lapsed. Must read as
        that edition, inactive -- not as community, which would hide the
        expiry."""
        env_token = mint_token(sub="*", edition="enterprise", status="canceled")
        org = _make_org(license_token=None)

        with patch.dict("os.environ", {"RHESIS_LICENSE": env_token}):
            info = provider.info(org=org)

        assert info["edition"] == "enterprise"
        assert info["licensed"] is False


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

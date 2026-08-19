"""Unit tests for capabilities_for_oauth_scope.

This is the mapping peqy flagged as missing on PR #2526: token-exchange JWTs
carry a coarse OAuth ``scope`` claim (``read``/``full``) but nothing translated
it into the capability strings Principal.scopes and the EE RBAC provider
actually consume, so every exchanged token silently inherited full access
regardless of what scope it requested.
"""

from unittest.mock import patch

import pytest

from rhesis.backend.app.auth.oauth_scope import capabilities_for_oauth_scope

_FAKE_CATALOG = [
    "endpoint:read",
    "endpoint:create",
    "endpoint:update",
    "endpoint:delete",
    "test_set:read",
    "test_set:execute",
    "recycle:view",  # deliberately NOT ":read" -- see test below
]


@pytest.mark.unit
@patch("rhesis.backend.app.auth.capabilities.get_all_capabilities", return_value=_FAKE_CATALOG)
class TestCapabilitiesForOAuthScope:
    def test_full_returns_none_sentinel(self, _mock_catalog):
        """None means "inherit full access" -- same sentinel as an unscoped rh-* token."""
        assert capabilities_for_oauth_scope("full") is None

    def test_full_wins_over_read(self, _mock_catalog):
        assert capabilities_for_oauth_scope("read full") is None
        assert capabilities_for_oauth_scope("full read") is None

    def test_read_returns_only_read_capabilities(self, _mock_catalog):
        result = capabilities_for_oauth_scope("read")
        assert result == frozenset({"endpoint:read", "test_set:read"})

    def test_read_excludes_non_read_suffixed_actions(self, _mock_catalog):
        """recycle:view is read-like but not literally ':read' -- excluded on purpose."""
        result = capabilities_for_oauth_scope("read")
        assert "recycle:view" not in result

    @pytest.mark.parametrize("scope_claim", [None, "", "   ", "offline_access"])
    def test_no_recognized_scope_grants_nothing(self, _mock_catalog, scope_claim):
        """Fail-closed: absent/empty/unrecognized scope is zero capabilities, not everything."""
        assert capabilities_for_oauth_scope(scope_claim) == frozenset()

    def test_unknown_token_alongside_read_still_grants_read(self, _mock_catalog):
        assert capabilities_for_oauth_scope("read unknown_future_scope") == frozenset(
            {"endpoint:read", "test_set:read"}
        )

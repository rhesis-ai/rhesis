"""Unit tests for orchestrator helpers that don't need DB / Redis / SSO.

The orchestrator's full happy path requires a working DB, an OIDC IdP
to validate against, and Redis for replay protection. Those belong in
an integration test. The helpers tested here -- shape validation,
audience parsing, scope splitting, TTL math -- are pure and most of
the security-relevant edge cases live in them, so it's worth pinning
their behaviour at the unit level.
"""

from __future__ import annotations

import time

import pytest

from rhesis.backend.ee.sso.token_exchange.exchange import (
    TokenExchangeError,
    TokenExchangeRequest,
    _audience_to_slug,
    _check_request_shape,
    _split_scope_string,
    _ttl_until_expiry,
)
from rhesis.backend.ee.sso.token_exchange.schemas import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    TOKEN_TYPE_ACCESS_TOKEN,
)


def _valid_payload(**overrides) -> TokenExchangeRequest:
    """Build a structurally valid request with sensible defaults."""
    base = dict(
        grant_type=GRANT_TYPE_TOKEN_EXCHANGE,
        subject_token="header.body.sig",
        subject_token_type=TOKEN_TYPE_ACCESS_TOKEN,
        audience="rhesis:org:acme",
        requested_token_type=None,
        scope=None,
        client_id="brain-prod",
        client_secret="s3cret",
    )
    base.update(overrides)
    return TokenExchangeRequest(**base)


# ---------------------------------------------------------------------------
# _check_request_shape
# ---------------------------------------------------------------------------


class TestCheckRequestShape:
    def test_accepts_valid_payload(self) -> None:
        # Should not raise.
        _check_request_shape(_valid_payload())

    def test_rejects_wrong_grant_type(self) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _check_request_shape(_valid_payload(grant_type="password"))
        assert exc.value.error == "unsupported_grant_type"
        assert exc.value.reason_code == "grant_type_unsupported"

    def test_rejects_wrong_subject_token_type(self) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _check_request_shape(
                _valid_payload(subject_token_type="urn:ietf:other")
            )
        assert exc.value.error == "invalid_request"

    def test_rejects_missing_subject_token(self) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _check_request_shape(_valid_payload(subject_token=""))
        assert exc.value.reason_code == "subject_token_missing"

    def test_rejects_missing_credentials(self) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _check_request_shape(_valid_payload(client_id=""))
        assert exc.value.reason_code == "client_credentials_missing"

    @pytest.mark.parametrize(
        "audience",
        [
            "",
            "acme",  # missing prefix
            "rhesis:org:",  # empty slug
            "rhesis:org:UPPER",  # case-sensitive
            "rhesis:org:has spaces",
            "rhesis:org:" + "x" * 51,  # too long for slug column
        ],
    )
    def test_rejects_malformed_audience(self, audience: str) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _check_request_shape(_valid_payload(audience=audience))
        assert exc.value.reason_code == "audience_malformed"


# ---------------------------------------------------------------------------
# _audience_to_slug
# ---------------------------------------------------------------------------


class TestAudienceToSlug:
    def test_strips_prefix(self) -> None:
        assert _audience_to_slug("rhesis:org:acme") == "acme"

    def test_returns_none_on_malformed(self) -> None:
        assert _audience_to_slug("acme") is None
        assert _audience_to_slug("") is None


# ---------------------------------------------------------------------------
# _split_scope_string
# ---------------------------------------------------------------------------


class TestSplitScopeString:
    def test_none_passes_through(self) -> None:
        # None is the "use default_scope" signal, not an error.
        assert _split_scope_string(None) is None

    def test_single_scope(self) -> None:
        assert _split_scope_string("read") == ["read"]

    def test_multiple_scopes_preserve_order(self) -> None:
        assert _split_scope_string("read offline_access") == [
            "read",
            "offline_access",
        ]

    def test_dedupes(self) -> None:
        assert _split_scope_string("read read offline_access") == [
            "read",
            "offline_access",
        ]

    def test_collapses_repeated_spaces(self) -> None:
        # split(" ") yields empty strings between repeats; the helper
        # drops them.
        assert _split_scope_string("read   offline_access") == [
            "read",
            "offline_access",
        ]

    @pytest.mark.parametrize("scope", ["", "   "])
    def test_rejects_empty(self, scope: str) -> None:
        with pytest.raises(TokenExchangeError) as exc:
            _split_scope_string(scope)
        assert exc.value.reason_code == "scope_empty"

    def test_rejects_tab_separator(self) -> None:
        # Mixed separators are a smuggle vector against naive splitters.
        with pytest.raises(TokenExchangeError) as exc:
            _split_scope_string("read\toffline_access")
        assert exc.value.reason_code == "scope_invalid_separator"


# ---------------------------------------------------------------------------
# _ttl_until_expiry
# ---------------------------------------------------------------------------


class TestTtlUntilExpiry:
    def test_returns_max_when_exp_missing(self) -> None:
        assert _ttl_until_expiry({}, max_seconds=600) == 600

    def test_returns_max_when_exp_not_numeric(self) -> None:
        assert _ttl_until_expiry({"exp": "soon"}, max_seconds=600) == 600

    def test_caps_at_max(self) -> None:
        # exp far in the future; result is clamped.
        far_future = int(time.time()) + 10_000
        assert _ttl_until_expiry({"exp": far_future}, max_seconds=600) == 600

    def test_returns_remaining_when_under_max(self) -> None:
        # 200 seconds remaining, max 600 -- expect ~200.
        target = int(time.time()) + 200
        ttl = _ttl_until_expiry({"exp": target}, max_seconds=600)
        # Allow a small fudge for the clock advancing during the test.
        assert 195 <= ttl <= 200

    def test_floors_to_one_when_already_expired(self) -> None:
        # Defensive: validator should reject expired tokens upstream
        # but we still return 1 so the Redis SET NX EX works.
        past = int(time.time()) - 100
        assert _ttl_until_expiry({"exp": past}, max_seconds=600) == 1

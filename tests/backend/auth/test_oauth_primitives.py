"""Core OAuth primitives: PKCE generation and signed state parameters.

These moved out of ``ee/sso`` so that any OAuth client flow can use them, not
just SSO login. The tests that came with them are here; the domain-separation
cases are new, and cover the property the move introduced.
"""

import os
import time
from unittest.mock import patch

import pytest

from rhesis.backend.app.auth.oauth_state import sign_state, verify_state
from rhesis.backend.app.auth.pkce import generate_pkce

SECRET = "a" * 48


@pytest.fixture(autouse=True)
def _session_secret():
    with patch.dict(os.environ, {"SESSION_SECRET_KEY": SECRET}):
        yield


class TestGeneratePkce:
    def test_returns_verifier_and_challenge(self):
        verifier, challenge = generate_pkce()

        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 40
        assert len(challenge) > 20

    def test_each_call_unique(self):
        a = generate_pkce()
        b = generate_pkce()

        assert a[0] != b[0]
        assert a[1] != b[1]

    def test_challenge_is_unpadded_base64url(self):
        # Providers reject '=' padding, and '+' or '/' would not survive a URL.
        _, challenge = generate_pkce()

        assert "=" not in challenge
        assert "+" not in challenge
        assert "/" not in challenge


class TestSignedState:
    def test_round_trips_the_payload(self):
        state = sign_state({"org_id": "org-1", "nonce": "n"}, purpose="sso")

        payload = verify_state(state, purpose="sso")

        assert payload["org_id"] == "org-1"
        assert payload["nonce"] == "n"

    def test_carries_an_arbitrary_payload(self):
        # The SSO version hardcoded its three fields; different flows carry
        # different context.
        state = sign_state({"tool_id": "t-1", "return_to": "/tools"}, purpose="tool")

        assert verify_state(state, purpose="tool")["tool_id"] == "t-1"

    def test_rejects_a_tampered_payload(self):
        state = sign_state({"org_id": "org-1"}, purpose="sso")
        tampered = state[:-4] + ("AAAA" if not state.endswith("AAAA") else "BBBB")

        with pytest.raises(ValueError):
            verify_state(tampered, purpose="sso")

    @pytest.mark.parametrize("garbage", ["", "not-base64!", "YWJj", "%%%%"])
    def test_rejects_malformed_state(self, garbage):
        with pytest.raises(ValueError):
            verify_state(garbage, purpose="sso")

    def test_rejects_an_expired_state(self):
        state = sign_state({"org_id": "org-1"}, purpose="sso")

        with patch("time.time", return_value=time.time() + 3600):
            with pytest.raises(ValueError, match="expired"):
                verify_state(state, purpose="sso")

    def test_a_state_minted_for_one_purpose_is_rejected_by_another(self):
        """The reason `purpose` exists.

        Both flows sign with a key derived from the same SESSION_SECRET_KEY. If
        they shared one derivation, a state minted by the tool-connection flow
        would verify in the SSO callback and vice versa, which is a
        cross-protocol replay rather than a theoretical concern.
        """
        state = sign_state({"tool_id": "t-1"}, purpose="tool")

        with pytest.raises(ValueError, match="signature"):
            verify_state(state, purpose="sso")

    def test_sso_derivation_is_unchanged_by_the_move(self):
        """Logins in flight when this shipped must not break.

        The original derived its key from f"sso-state-{SESSION_SECRET_KEY}".
        Passing purpose="sso" has to reproduce that byte for byte.
        """
        import hashlib

        from rhesis.backend.app.auth.oauth_state import _signing_key

        assert _signing_key("sso") == hashlib.sha256(f"sso-state-{SECRET}".encode()).digest()

    def test_fails_loudly_without_a_session_secret(self):
        # Falling back to a constant key would let anyone forge a state.
        with patch.dict(os.environ, {"SESSION_SECRET_KEY": ""}):
            with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY"):
                sign_state({"a": "b"}, purpose="sso")

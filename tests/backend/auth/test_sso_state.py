"""Tests for SSO signed state parameter."""

import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

import pytest

from rhesis.backend.app.auth.providers.oidc import (
    STATE_MAX_AGE_SECONDS,
    create_signed_state,
    verify_signed_state,
)


def _decode_state(state: str) -> str:
    padded = state + "=" * (-len(state) % 4)
    return urlsafe_b64decode(padded).decode()


def _encode_state(raw: str) -> str:
    return urlsafe_b64encode(raw.encode()).decode()


class TestSignedState:
    """Test signed state creation and verification."""

    def test_roundtrip(self):
        state = create_signed_state("org-123", "nonce-abc", "/settings")
        payload = verify_signed_state(state)
        assert payload["org_id"] == "org-123"
        assert payload["nonce"] == "nonce-abc"
        assert payload["return_to"] == "/settings"

    def test_state_is_base64_encoded(self):
        state = create_signed_state("org-123", "nonce-abc")
        raw = _decode_state(state)
        assert "|" in raw
        assert '"org_id"' in raw

    def test_tampered_payload_rejected(self):
        state = create_signed_state("org-123", "nonce-abc")
        raw = _decode_state(state)
        tampered_raw = raw.replace("org-123", "org-999")
        tampered = _encode_state(tampered_raw)
        with pytest.raises(ValueError, match="signature"):
            verify_signed_state(tampered)

    def test_tampered_signature_rejected(self):
        state = create_signed_state("org-123", "nonce-abc")
        raw = _decode_state(state)
        data, sig = raw.rsplit("|", 1)
        bad_sig = "0" * len(sig)
        tampered = _encode_state(f"{data}|{bad_sig}")
        with pytest.raises(ValueError, match="signature"):
            verify_signed_state(tampered)

    def test_non_base64_rejected(self):
        with pytest.raises(ValueError, match="encoding"):
            verify_signed_state("not!valid@base64$$")

    def test_missing_separator_rejected(self):
        encoded = _encode_state("no-separator-here")
        with pytest.raises(ValueError, match="format"):
            verify_signed_state(encoded)

    def test_expired_state_rejected(self, monkeypatch):
        state = create_signed_state("org-123", "nonce-abc")
        original_time = time.time
        monkeypatch.setattr(
            time,
            "time",
            lambda: original_time() + STATE_MAX_AGE_SECONDS + 60,
        )
        with pytest.raises(ValueError, match="expired"):
            verify_signed_state(state)

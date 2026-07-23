"""Tests for the SSO encryption helpers under ``rhesis.backend.ee.sso.encryption``.

The exception types (``DecryptionError``, ``EncryptionError``) come from
core because they are general-purpose and shared across all encryption
domains in the codebase. The version-prefixed encrypt/decrypt logic and
the ``SSO_ENCRYPTION_KEY`` lookup are EE-only.
"""

import pytest


class TestSSOEncryption:
    """Test versioned SSO encrypt/decrypt functions."""

    def test_roundtrip(self):
        from rhesis.backend.ee.sso.encryption import sso_decrypt, sso_encrypt

        plaintext = "my-client-secret-1234"
        encrypted = sso_encrypt(plaintext)
        assert encrypted.startswith("v1:")
        assert plaintext not in encrypted
        assert sso_decrypt(encrypted) == plaintext

    def test_decrypt_invalid_version(self):
        from rhesis.backend.app.utils.encryption import DecryptionError
        from rhesis.backend.ee.sso.encryption import sso_decrypt

        with pytest.raises(DecryptionError, match="version prefix"):
            sso_decrypt("no-version-prefix-here")

    def test_decrypt_unknown_version(self):
        from rhesis.backend.app.utils.encryption import EncryptionError
        from rhesis.backend.ee.sso.encryption import sso_decrypt

        with pytest.raises(EncryptionError, match="Unknown SSO key version"):
            sso_decrypt("v99:somedata")

    def test_decrypt_tampered_ciphertext(self):
        from rhesis.backend.app.utils.encryption import DecryptionError
        from rhesis.backend.ee.sso.encryption import sso_decrypt, sso_encrypt

        encrypted = sso_encrypt("test-secret")
        version, ciphertext = encrypted.split(":", 1)
        tampered = f"{version}:{ciphertext[:-4]}XXXX"
        with pytest.raises(DecryptionError, match="Invalid SSO encrypted data"):
            sso_decrypt(tampered)

    def test_is_sso_encryption_available(self):
        from rhesis.backend.ee.sso.encryption import is_sso_encryption_available

        assert is_sso_encryption_available() is True

    def test_is_sso_encryption_unavailable(self, monkeypatch):
        from rhesis.backend.app.config.settings import get_security_settings
        from rhesis.backend.ee.sso.encryption import (
            _get_sso_fernet,
            is_sso_encryption_available,
        )

        _get_sso_fernet.cache_clear()
        monkeypatch.delenv("SSO_ENCRYPTION_KEY", raising=False)
        # The key is now read via the lru-cached SecuritySettings, so the
        # settings cache must be cleared for the deleted env var to take effect.
        get_security_settings.cache_clear()
        result = is_sso_encryption_available()
        assert result is False

        # Re-apply env for other tests
        monkeypatch.setenv(
            "SSO_ENCRYPTION_KEY", "9KgQ8O8Dx3xfUejfiAwkDgYMqD_2vekaNYw2WvqvJdw="
        )
        _get_sso_fernet.cache_clear()
        get_security_settings.cache_clear()

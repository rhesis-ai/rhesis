"""Tests for SSO encryption/decryption utilities."""

import pytest


class TestSSOEncryption:
    """Test versioned SSO encrypt/decrypt functions."""

    def test_roundtrip(self):
        from rhesis.backend.app.utils.encryption import sso_decrypt, sso_encrypt

        plaintext = "my-client-secret-1234"
        encrypted = sso_encrypt(plaintext)
        assert encrypted.startswith("v1:")
        assert plaintext not in encrypted
        assert sso_decrypt(encrypted) == plaintext

    def test_decrypt_invalid_version(self):
        from rhesis.backend.app.utils.encryption import DecryptionError, sso_decrypt

        with pytest.raises(DecryptionError, match="version prefix"):
            sso_decrypt("no-version-prefix-here")

    def test_decrypt_unknown_version(self):
        from rhesis.backend.app.utils.encryption import EncryptionError, sso_decrypt

        with pytest.raises(EncryptionError, match="Unknown SSO key version"):
            sso_decrypt("v99:somedata")

    def test_decrypt_tampered_ciphertext(self):
        from rhesis.backend.app.utils.encryption import (
            DecryptionError,
            sso_decrypt,
            sso_encrypt,
        )

        encrypted = sso_encrypt("test-secret")
        version, ciphertext = encrypted.split(":", 1)
        tampered = f"{version}:{ciphertext[:-4]}XXXX"
        with pytest.raises(DecryptionError, match="Invalid SSO encrypted data"):
            sso_decrypt(tampered)

    def test_is_sso_encryption_available(self):
        from rhesis.backend.app.utils.encryption import is_sso_encryption_available

        assert is_sso_encryption_available() is True

    def test_is_sso_encryption_unavailable(self, monkeypatch):
        from functools import lru_cache

        from rhesis.backend.app.utils.encryption import (
            _get_sso_fernet,
            is_sso_encryption_available,
        )

        # Clear cache so the monkeypatched env takes effect
        _get_sso_fernet.cache_clear()
        monkeypatch.delenv("SSO_ENCRYPTION_KEY", raising=False)
        result = is_sso_encryption_available()
        assert result is False

        # Re-apply env for other tests
        monkeypatch.setenv(
            "SSO_ENCRYPTION_KEY", "9KgQ8O8Dx3xfUejfiAwkDgYMqD_2vekaNYw2WvqvJdw="
        )
        _get_sso_fernet.cache_clear()

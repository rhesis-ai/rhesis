import os
import pytest
from cryptography.fernet import Fernet
from rhesis.backend.app.utils.encryption import (
    encrypt,
    decrypt,
    is_encrypted,
    get_encryption_key,
    EncryptionKeyNotFoundError,
    EncryptionError,
    DecryptionError,
    EncryptedString,
)


@pytest.fixture
def encryption_key():
    """Provide a test encryption key."""
    # Preserve original value
    original_key = os.environ.get("DB_ENCRYPTION_KEY")
    key = Fernet.generate_key().decode()
    os.environ["DB_ENCRYPTION_KEY"] = key
    yield key
    # Restore original value or remove if it wasn't set
    if original_key is not None:
        os.environ["DB_ENCRYPTION_KEY"] = original_key
    elif "DB_ENCRYPTION_KEY" in os.environ:
        del os.environ["DB_ENCRYPTION_KEY"]


class TestEncryptionUtilities:
    """Test encryption utility functions."""

    def test_get_encryption_key_success(self, encryption_key):
        """Test getting encryption key from environment."""
        key = get_encryption_key()
        assert key == encryption_key.encode()

    def test_get_encryption_key_not_set(self):
        """Test error when encryption key is not set."""
        # Preserve original value
        original_key = os.environ.get("DB_ENCRYPTION_KEY")
        if "DB_ENCRYPTION_KEY" in os.environ:
            del os.environ["DB_ENCRYPTION_KEY"]

        try:
            with pytest.raises(EncryptionKeyNotFoundError):
                get_encryption_key()
        finally:
            # Restore original value
            if original_key is not None:
                os.environ["DB_ENCRYPTION_KEY"] = original_key

    def test_encrypt_decrypt_roundtrip(self, encryption_key):
        """Test encryption and decryption roundtrip."""
        plaintext = "my-secret-api-key-12345"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)

    def test_encrypt_none(self, encryption_key):
        """Test encrypting None value."""
        assert encrypt(None) is None

    def test_decrypt_none(self, encryption_key):
        """Test decrypting None value."""
        assert decrypt(None) is None

    def test_encrypt_empty_string(self, encryption_key):
        """Test encrypting empty string."""
        assert encrypt("") == ""

    def test_decrypt_empty_string(self, encryption_key):
        """Test decrypting empty string."""
        assert decrypt("") == ""

    def test_encrypt_unicode(self, encryption_key):
        """Test encrypting Unicode characters."""
        plaintext = "🔐 Secret key with émojis and àccents"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

    def test_decrypt_invalid_token(self, encryption_key):
        """Test decrypting invalid token."""
        with pytest.raises(DecryptionError):
            decrypt("invalid-encrypted-data")

    def test_decrypt_wrong_key(self, encryption_key):
        """Test decrypting with wrong key."""
        plaintext = "secret"
        encrypted = encrypt(plaintext)

        # Change key
        os.environ["DB_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        with pytest.raises(DecryptionError):
            decrypt(encrypted)

    def test_is_encrypted_true(self, encryption_key):
        """Test detecting encrypted values."""
        plaintext = "secret"
        encrypted = encrypt(plaintext)
        assert is_encrypted(encrypted) is True

    def test_is_encrypted_false(self, encryption_key):
        """Test detecting plaintext values."""
        plaintext = "plaintext-api-key"
        assert is_encrypted(plaintext) is False

    def test_is_encrypted_none(self, encryption_key):
        """Test is_encrypted with None."""
        assert is_encrypted(None) is False

    def test_is_encrypted_empty(self, encryption_key):
        """Test is_encrypted with empty string."""
        assert is_encrypted("") is False

    def test_is_encrypted_short_string(self, encryption_key):
        """Test is_encrypted with string shorter than 10 chars."""
        assert is_encrypted("short") is False

    def test_encrypt_long_text(self, encryption_key):
        """Test encrypting long text."""
        plaintext = "a" * 1000  # 1000 character string
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext
        assert len(encrypted) > len(plaintext)

    def test_encrypt_special_characters(self, encryption_key):
        """Test encrypting special characters."""
        plaintext = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_without_key_raises_error(self):
        """Test that encryption without key raises appropriate error."""
        # Preserve original value
        original_key = os.environ.get("DB_ENCRYPTION_KEY")
        if "DB_ENCRYPTION_KEY" in os.environ:
            del os.environ["DB_ENCRYPTION_KEY"]

        try:
            with pytest.raises(EncryptionError):
                encrypt("some-data")
        finally:
            # Restore original value
            if original_key is not None:
                os.environ["DB_ENCRYPTION_KEY"] = original_key

    def test_decrypt_without_key_raises_error(self):
        """Test that decryption without key raises appropriate error."""
        # Preserve original value
        original_key = os.environ.get("DB_ENCRYPTION_KEY")
        if "DB_ENCRYPTION_KEY" in os.environ:
            del os.environ["DB_ENCRYPTION_KEY"]

        try:
            with pytest.raises(DecryptionError):
                decrypt("gAAAAABmV8x...")  # Fake encrypted data
        finally:
            # Restore original value
            if original_key is not None:
                os.environ["DB_ENCRYPTION_KEY"] = original_key


class TestEncryptedStringType:
    """Test SQLAlchemy EncryptedString type."""

    def test_process_bind_param_encrypts(self, encryption_key):
        """Test that bind param encrypts value."""
        encrypted_type = EncryptedString()
        plaintext = "my-api-key"

        result = encrypted_type.process_bind_param(plaintext, None)

        assert result is not None
        assert result != plaintext
        assert is_encrypted(result)

    def test_process_bind_param_none(self, encryption_key):
        """Test that None stays None."""
        encrypted_type = EncryptedString()
        result = encrypted_type.process_bind_param(None, None)
        assert result is None

    def test_process_result_value_decrypts(self, encryption_key):
        """Test that result value decrypts."""
        encrypted_type = EncryptedString()
        plaintext = "my-api-key"

        # Encrypt first
        encrypted = encrypted_type.process_bind_param(plaintext, None)
        # Then decrypt
        decrypted = encrypted_type.process_result_value(encrypted, None)

        assert decrypted == plaintext

    def test_process_result_value_none(self, encryption_key):
        """Test that None stays None."""
        encrypted_type = EncryptedString()
        result = encrypted_type.process_result_value(None, None)
        assert result is None

    def test_backward_compatibility_plaintext(self, encryption_key):
        """Test that plaintext values are handled during migration."""
        encrypted_type = EncryptedString()
        plaintext = "plaintext-token"

        # Simulate reading plaintext from DB (not encrypted)
        # This should NOT raise an exception and should return the plaintext
        result = encrypted_type.process_result_value(plaintext, None)

        # Should return plaintext as-is during migration window
        assert result == plaintext
        # Verify it's not encrypted
        assert not is_encrypted(plaintext)

    def test_encrypted_string_with_length(self, encryption_key):
        """Test EncryptedString with length parameter."""
        encrypted_type = EncryptedString(length=500)
        assert encrypted_type.impl.length == 500

    def test_encrypted_string_without_length(self, encryption_key):
        """Test EncryptedString without length parameter (Text field)."""
        encrypted_type = EncryptedString()
        # Should use String type but without length restriction
        assert encrypted_type.impl is not None

    def test_roundtrip_with_empty_string(self, encryption_key):
        """Test complete roundtrip with empty string."""
        encrypted_type = EncryptedString()

        encrypted = encrypted_type.process_bind_param("", None)
        decrypted = encrypted_type.process_result_value(encrypted, None)

        assert decrypted == ""

    def test_roundtrip_with_unicode(self, encryption_key):
        """Test complete roundtrip with Unicode."""
        encrypted_type = EncryptedString()
        plaintext = "测试 тест テスト 🔐"

        encrypted = encrypted_type.process_bind_param(plaintext, None)
        decrypted = encrypted_type.process_result_value(encrypted, None)

        assert decrypted == plaintext

    def test_process_bind_param_raises_on_encryption_failure(self, encryption_key):
        """Test that bind param raises EncryptionError on failure."""
        encrypted_type = EncryptedString()

        # Preserve original value
        original_key = os.environ.get("DB_ENCRYPTION_KEY")
        # Remove encryption key to force failure
        del os.environ["DB_ENCRYPTION_KEY"]

        try:
            with pytest.raises(EncryptionError):
                encrypted_type.process_bind_param("some-value", None)
        finally:
            # Restore original value
            if original_key is not None:
                os.environ["DB_ENCRYPTION_KEY"] = original_key

    def test_cache_ok_is_true(self, encryption_key):
        """Test that cache_ok is set to True for SQLAlchemy caching."""
        encrypted_type = EncryptedString()
        assert encrypted_type.cache_ok is True

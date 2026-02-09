"""
Unit tests for password hashing utilities.

Tests the hash_password() and verify_password() functions in encryption.py.
"""

import pytest
from faker import Faker

fake = Faker()


class TestPasswordHashing:
    """Tests for password hashing functions."""

    @pytest.mark.unit
    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        from rhesis.backend.app.utils.encryption import hash_password

        password = fake.password(length=12)
        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0

    @pytest.mark.unit
    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes (salt)."""
        from rhesis.backend.app.utils.encryption import hash_password

        password = fake.password(length=12)
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to unique salts
        assert hash1 != hash2

    @pytest.mark.unit
    def test_hash_password_bcrypt_format(self):
        """Test that hash is in bcrypt format."""
        from rhesis.backend.app.utils.encryption import hash_password

        password = fake.password(length=12)
        hashed = hash_password(password)

        # bcrypt hashes start with $2b$ (or $2a$, $2y$)
        assert hashed.startswith("$2")

    @pytest.mark.unit
    def test_hash_password_empty_raises_error(self):
        """Test that empty password raises ValueError."""
        from rhesis.backend.app.utils.encryption import hash_password

        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")

    @pytest.mark.unit
    def test_hash_password_none_raises_error(self):
        """Test that None password raises ValueError."""
        from rhesis.backend.app.utils.encryption import hash_password

        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password(None)


class TestPasswordVerification:
    """Tests for password verification functions."""

    @pytest.mark.unit
    def test_verify_password_correct(self):
        """Test that correct password verifies successfully."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        password = fake.password(length=12)
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    @pytest.mark.unit
    def test_verify_password_incorrect(self):
        """Test that incorrect password fails verification."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        password = fake.password(length=12)
        wrong_password = fake.password(length=12)
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    @pytest.mark.unit
    def test_verify_password_empty_plain_returns_false(self):
        """Test that empty plain password returns False."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        password = fake.password(length=12)
        hashed = hash_password(password)

        assert verify_password("", hashed) is False

    @pytest.mark.unit
    def test_verify_password_empty_hash_returns_false(self):
        """Test that empty hash returns False."""
        from rhesis.backend.app.utils.encryption import verify_password

        password = fake.password(length=12)

        assert verify_password(password, "") is False

    @pytest.mark.unit
    def test_verify_password_none_plain_returns_false(self):
        """Test that None plain password returns False."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        password = fake.password(length=12)
        hashed = hash_password(password)

        assert verify_password(None, hashed) is False

    @pytest.mark.unit
    def test_verify_password_none_hash_returns_false(self):
        """Test that None hash returns False."""
        from rhesis.backend.app.utils.encryption import verify_password

        password = fake.password(length=12)

        assert verify_password(password, None) is False

    @pytest.mark.unit
    def test_verify_password_invalid_hash_returns_false(self):
        """Test that invalid hash format returns False."""
        from rhesis.backend.app.utils.encryption import verify_password

        password = fake.password(length=12)

        # Various invalid hash formats
        invalid_hashes = [
            "not_a_hash",
            "12345",
            "$2b$invalid",
            "a" * 60,  # Wrong format but right length
        ]

        for invalid_hash in invalid_hashes:
            assert verify_password(password, invalid_hash) is False


class TestPasswordSecurityProperties:
    """Tests for security properties of password hashing."""

    @pytest.mark.unit
    def test_hash_is_not_reversible(self):
        """Test that hash doesn't contain the original password."""
        from rhesis.backend.app.utils.encryption import hash_password

        password = "MySecretPassword123!"
        hashed = hash_password(password)

        # Hash should not contain the password
        assert password not in hashed

    @pytest.mark.unit
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        from rhesis.backend.app.utils.encryption import hash_password

        password1 = fake.password(length=12)
        password2 = fake.password(length=12)

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        assert hash1 != hash2

    @pytest.mark.unit
    def test_hash_length_is_consistent(self):
        """Test that hash length is consistent regardless of password length."""
        from rhesis.backend.app.utils.encryption import hash_password

        short_password = "short"
        long_password = fake.password(length=100)

        short_hash = hash_password(short_password)
        long_hash = hash_password(long_password)

        # bcrypt hashes are always 60 characters
        assert len(short_hash) == 60
        assert len(long_hash) == 60

    @pytest.mark.unit
    def test_unicode_password_support(self):
        """Test that unicode passwords are supported."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        unicode_password = "密码Password123!🔐"
        hashed = hash_password(unicode_password)

        assert verify_password(unicode_password, hashed) is True

    @pytest.mark.unit
    def test_very_long_password(self):
        """Test that very long passwords work correctly."""
        from rhesis.backend.app.utils.encryption import hash_password, verify_password

        # bcrypt has a 72-byte limit, but should handle longer gracefully
        long_password = fake.password(length=200)
        hashed = hash_password(long_password)

        assert verify_password(long_password, hashed) is True

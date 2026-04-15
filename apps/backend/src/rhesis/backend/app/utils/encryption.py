# apps/backend/src/rhesis/backend/app/utils/encryption.py

import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from sqlalchemy import String, TypeDecorator

logger = logging.getLogger(__name__)


# Password hashing context using bcrypt
# bcrypt is intentionally separate from Fernet encryption:
# - Fernet (EncryptedString): Reversible encryption for secrets that need retrieval
# - bcrypt (password hashing): One-way hashing for passwords (irreversible by design)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EncryptionKeyNotFoundError(Exception):
    """Raised when DB_ENCRYPTION_KEY environment variable is not set."""

    pass


class EncryptionError(Exception):
    """Raised when encryption operation fails."""

    pass


class DecryptionError(Exception):
    """Raised when decryption operation fails."""

    pass


# =============================================================================
# Password Hashing Functions (bcrypt - one-way, irreversible)
# =============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    This is a ONE-WAY hash - the original password cannot be recovered.
    Use verify_password() to check if a password matches a hash.

    Args:
        password: The plaintext password to hash

    Returns:
        The bcrypt hash string (includes salt and algorithm info)

    Raises:
        ValueError: If password is empty or None

    Note:
        - bcrypt automatically generates a unique salt for each hash
        - The same password will produce different hashes each time
        - Hash includes algorithm version, cost factor, salt, and hash
        - This is intentionally separate from EncryptedString (Fernet)
          because passwords should never be decryptable
    """
    if not password:
        raise ValueError("Password cannot be empty")

    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: The plaintext password to verify
        hashed_password: The bcrypt hash to verify against

    Returns:
        True if the password matches, False otherwise

    Note:
        - Returns False (not raises) for invalid passwords
        - Constant-time comparison prevents timing attacks
        - Works with hashes from any bcrypt implementation
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification failed: {str(e)}")
        return False


# =============================================================================
# Fernet Encryption Functions (reversible, for secrets that need retrieval)
# =============================================================================


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable.

    Returns:
        bytes: The encryption key

    Raises:
        EncryptionKeyNotFoundError: If DB_ENCRYPTION_KEY is not set
    """
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        raise EncryptionKeyNotFoundError(
            "DB_ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return key.encode()


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Return a cached Fernet instance built from the encryption key.

    Creating a Fernet object involves key validation and HMAC key derivation,
    so constructing one per encrypt/decrypt call is wasteful. This cache
    ensures a single instance is reused for the lifetime of the process.

    Note: Dynamic key rotation via environment variable reloading without
    restarting the process is not supported. If rotation is needed, the
    backend service must be restarted to clear this cache.
    """
    return Fernet(get_encryption_key())


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypt a plaintext string.

    Args:
        plaintext: The string to encrypt (can be None)

    Returns:
        Base64-encoded encrypted string, or None if input is None

    Raises:
        EncryptionError: If encryption fails
    """
    if plaintext is None:
        return None

    if plaintext == "":
        return ""  # Empty string remains empty

    try:
        encrypted_bytes = _get_fernet().encrypt(plaintext.encode())
        return encrypted_bytes.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        raise EncryptionError(f"Failed to encrypt data: {str(e)}")


def decrypt(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypt an encrypted string.

    Args:
        ciphertext: The encrypted string to decrypt (can be None)

    Returns:
        Decrypted plaintext string, or None if input is None

    Raises:
        DecryptionError: If decryption fails
    """
    if ciphertext is None:
        return None

    if ciphertext == "":
        return ""  # Empty string remains empty

    try:
        decrypted_bytes = _get_fernet().decrypt(ciphertext.encode())
        return decrypted_bytes.decode()
    except InvalidToken:
        raise DecryptionError("Invalid encrypted data or wrong encryption key")
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        raise DecryptionError(f"Failed to decrypt data: {str(e)}")


def is_encrypted(value: Optional[str]) -> bool:
    """
    Check if a value is encrypted (Fernet format).

    Fernet tokens start with 'gAAAAA' when base64 encoded.
    This is a heuristic check - not 100% reliable but good enough for migration.

    Args:
        value: The string to check

    Returns:
        True if value appears to be encrypted, False otherwise
    """
    if not value or len(value) < 10:
        return False

    # Fernet tokens have specific format: version (1 byte) + timestamp (8 bytes) + ...
    # When base64 encoded, they typically start with 'gAAAAA'
    # This is not foolproof but works for migration detection
    try:
        return value.startswith("gAAAAA")
    except Exception:
        return False


def hash_token(token_value: str) -> str:
    """
    Create a SHA-256 hash of a token value for fast lookups.

    This hash is used as a deterministic index for looking up encrypted tokens.
    Since encryption is non-deterministic (Fernet), we can't query encrypted values directly.
    Instead, we store a hash alongside the encrypted value for O(1) indexed lookups.

    Args:
        token_value: The plaintext token value to hash

    Returns:
        Hexadecimal SHA-256 hash (64 characters)

    Note:
        - SHA-256 is one-way: hash cannot be reversed to get the original token
        - Same input always produces same hash (deterministic)
        - Used for database lookups, not for security validation
        - The actual token is stored encrypted for security
    """
    if not token_value:
        raise ValueError("Token value cannot be empty")

    return hashlib.sha256(token_value.encode()).hexdigest()


# =============================================================================
# SSO-specific Encryption (versioned keys for client_secret at rest)
# =============================================================================

_SSO_KEY_VERSIONS = {
    "v1": "SSO_ENCRYPTION_KEY",
}


@lru_cache(maxsize=4)
def _get_sso_fernet(version: str) -> Fernet:
    """Return a cached Fernet instance for the given SSO key version.

    Mirrors the existing ``_get_fernet()`` pattern for DB_ENCRYPTION_KEY.
    """
    env_var = _SSO_KEY_VERSIONS.get(version)
    if not env_var:
        raise EncryptionError(f"Unknown SSO key version: {version}")
    key = os.getenv(env_var)
    if not key:
        raise EncryptionKeyNotFoundError(f"{env_var} environment variable is not set")
    try:
        return Fernet(key.encode())
    except Exception:
        raise EncryptionError(f"{env_var} is not a valid Fernet key")


def get_sso_encryption_key(version: str = "v1") -> bytes:
    """Get SSO-specific encryption key by version (validates format)."""
    _get_sso_fernet(version)
    env_var = _SSO_KEY_VERSIONS[version]
    return os.getenv(env_var).encode()


def sso_encrypt(plaintext: str, version: str = "v1") -> str:
    """Encrypt a value with a versioned SSO key.

    Returns ``"{version}:{ciphertext}"`` -- the version prefix enables
    future key rotation without re-encrypting all secrets at once.
    """
    f = _get_sso_fernet(version)
    ciphertext = f.encrypt(plaintext.encode()).decode()
    return f"{version}:{ciphertext}"


def sso_decrypt(versioned_ciphertext: str) -> str:
    """Decrypt a version-prefixed SSO ciphertext.

    Fail closed: raises DecryptionError on any failure.
    """
    if ":" not in versioned_ciphertext:
        raise DecryptionError("SSO ciphertext missing version prefix")
    version, ciphertext = versioned_ciphertext.split(":", 1)
    f = _get_sso_fernet(version)
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise DecryptionError("Invalid SSO encrypted data or wrong encryption key")


def is_sso_encryption_available() -> bool:
    """Check if SSO encryption is configured (without crashing)."""
    try:
        get_sso_encryption_key("v1")
        return True
    except (EncryptionKeyNotFoundError, EncryptionError):
        return False


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy custom type for transparent encryption/decryption.

    Usage in models:
        auth_token = Column(EncryptedString(length=500))

    Features:
    - Automatically encrypts on write
    - Automatically decrypts on read
    - Handles None values
    - Backward compatible (handles plaintext during migration)
    """

    impl = String
    cache_ok = True

    def __init__(self, length=None, **kwargs):
        """
        Initialize with optional length parameter.

        Args:
            length: Maximum length for the underlying String column
                   (default: None for unlimited Text field)
        """
        super().__init__(**kwargs)
        if length:
            self.impl = String(length)

    def process_bind_param(self, value, dialect):
        """
        Encrypt value before storing in database.

        Args:
            value: Plaintext value from application
            dialect: SQLAlchemy dialect

        Returns:
            Encrypted value for database
        """
        if value is None:
            return None

        # Always encrypt when writing
        try:
            encrypted = encrypt(value)
            logger.debug(
                f"Encrypted value for storage (length: {len(encrypted) if encrypted else 0})"
            )
            return encrypted
        except EncryptionError as e:
            logger.error(f"Failed to encrypt value: {str(e)}")
            raise

    def process_result_value(self, value, dialect):
        """
        Decrypt value when reading from database.

        Args:
            value: Encrypted value from database
            dialect: SQLAlchemy dialect

        Returns:
            Decrypted plaintext value for application
        """
        if value is None:
            return None

        # Try to decrypt
        try:
            decrypted = decrypt(value)
            logger.debug("Successfully decrypted value from database")
            return decrypted
        except DecryptionError:
            # BACKWARD COMPATIBILITY: During migration, some values may still be plaintext
            # Log warning and return plaintext value
            logger.warning(
                "Found unencrypted value in encrypted column. "
                "This should only happen during migration. "
                "Run data migration script to encrypt all values."
            )
            return value  # Return as-is (plaintext)

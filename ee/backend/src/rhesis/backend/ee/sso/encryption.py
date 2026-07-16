"""SSO client_secret encryption with versioned keys.

This is the EE-side counterpart to the core's
:mod:`rhesis.backend.app.utils.encryption` module. It exists separately
because:

1. SSO is an Enterprise Edition feature; its encryption helpers must live
   under ``ee/`` so that core builds (without the ``ee`` extra) carry no
   SSO-specific code.
2. The version prefix enables future key rotation without re-encrypting
   every stored ``client_secret`` at once. Today only ``v1`` exists, mapped
   to the ``sso_encryption_key`` setting (``SSO_ENCRYPTION_KEY``).

The exception types (``EncryptionError``, ``EncryptionKeyNotFoundError``,
``DecryptionError``) are reused from core: they are general-purpose and
not coupled to SSO.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from rhesis.backend.app.config.settings import get_security_settings
from rhesis.backend.app.utils.encryption import (
    DecryptionError,
    EncryptionError,
    EncryptionKeyNotFoundError,
)

# Maps a ciphertext version prefix to the ``SecuritySettings`` attribute that
# holds the key for that version. Future rotation adds ``"v2": ...`` here.
_SSO_KEY_VERSIONS = {
    "v1": "sso_encryption_key",
}


@lru_cache(maxsize=4)
def _get_sso_fernet(version: str) -> Fernet:
    """Return a cached Fernet instance for the given SSO key version.

    Mirrors the ``_get_fernet()`` pattern in core (``DB_ENCRYPTION_KEY``):
    the cache lasts the life of the process, so dynamic key rotation
    without a restart is not supported.
    """
    attr = _SSO_KEY_VERSIONS.get(version)
    if not attr:
        raise EncryptionError(f"Unknown SSO key version: {version}")
    key = getattr(get_security_settings(), attr)
    if not key:
        raise EncryptionKeyNotFoundError("SSO_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except Exception:
        raise EncryptionError("SSO_ENCRYPTION_KEY is not a valid Fernet key")


def get_sso_encryption_key(version: str = "v1") -> bytes:
    """Return the raw SSO encryption key bytes for *version*.

    Validates the key by constructing the Fernet first; raises
    ``EncryptionError`` or ``EncryptionKeyNotFoundError`` on failure.
    """
    _get_sso_fernet(version)
    attr = _SSO_KEY_VERSIONS[version]
    return getattr(get_security_settings(), attr).encode()


def sso_encrypt(plaintext: str, version: str = "v1") -> str:
    """Encrypt *plaintext* with the SSO key for *version*.

    Returns ``"{version}:{ciphertext}"``; the version prefix lets
    :func:`sso_decrypt` route to the right key when multiple versions
    coexist during rotation.
    """
    f = _get_sso_fernet(version)
    ciphertext = f.encrypt(plaintext.encode()).decode()
    return f"{version}:{ciphertext}"


def sso_decrypt(versioned_ciphertext: str) -> str:
    """Decrypt a version-prefixed SSO ciphertext.

    Fail closed: raises :class:`DecryptionError` on missing prefix,
    unknown version, or invalid ciphertext.
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
    """Return ``True`` iff ``SSO_ENCRYPTION_KEY`` is configured and valid.

    Used by the SSO feature's runtime check so that, even with the EE
    package installed, SSO is reported as unavailable until the
    operator provides a valid key.
    """
    try:
        get_sso_encryption_key("v1")
        return True
    except (EncryptionKeyNotFoundError, EncryptionError):
        return False


__all__ = [
    "_get_sso_fernet",
    "_SSO_KEY_VERSIONS",
    "get_sso_encryption_key",
    "is_sso_encryption_available",
    "sso_decrypt",
    "sso_encrypt",
]

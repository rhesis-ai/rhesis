"""Public key loader for license JWT verification.

Baked-in Ed25519 public keys live alongside this package in
``public_keys/<kid>.pem``.  An operator may override or supplement them by
setting ``RHESIS_LICENSE_PUBLIC_KEY`` to a PEM-encoded public key; the
override is registered under the synthetic kid ``"env"``.

The resulting map is keyed by ``kid`` string and its values are
:class:`~cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey`
instances ready for use by :mod:`~rhesis.backend.ee.licensing.verify`.

When no public keys are available (empty map) the provider fails closed
and logs a one-time warning rather than silently permitting all traffic.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from importlib import resources as importlib_resources
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from rhesis.backend.ee.licensing.entitlements import ENV_LICENSE_PUBLIC_KEY

logger = logging.getLogger(__name__)

# Names of the baked-in keypairs bundled with this package.
_BAKED_KIDS = ("rhesis-prod-v1", "rhesis-nonprod-v1")

# Synthetic kid under which a RHESIS_LICENSE_PUBLIC_KEY override is registered.
_ENV_KID = "env"


def _load_pem(pem_text: str | bytes) -> Optional[Ed25519PublicKey]:
    """Parse a PEM public key, returning ``None`` on error."""
    try:
        key = load_pem_public_key(
            pem_text if isinstance(pem_text, bytes) else pem_text.encode()
        )
        if not isinstance(key, Ed25519PublicKey):
            logger.error("License public key is not an Ed25519 key — ignored")
            return None
        return key
    except Exception as exc:
        logger.error("Failed to load license public key: %s", exc)
        return None


@lru_cache(maxsize=1)
def get_public_keys() -> dict[str, Ed25519PublicKey]:
    """Return the map of ``kid -> Ed25519PublicKey`` available for verification.

    Results are cached for the lifetime of the process.  The cache is
    intentionally keyed by nothing (``maxsize=1``, called with no args) so
    repeated calls are free after the first load.

    The function is module-level so tests can bypass it via
    ``get_public_keys.cache_clear()`` after patching env vars or resources.
    """
    keys: dict[str, Ed25519PublicKey] = {}

    # --- Baked-in keys from package resources ---
    pkg = importlib_resources.files("rhesis.backend.ee.licensing.public_keys")
    for kid in _BAKED_KIDS:
        try:
            pem_bytes = (pkg / f"{kid}.pem").read_bytes()
            key = _load_pem(pem_bytes)
            if key is not None:
                keys[kid] = key
                logger.debug("Loaded baked-in license public key: kid=%s", kid)
        except (FileNotFoundError, TypeError) as exc:
            logger.warning("Baked-in license public key not found: kid=%s (%s)", kid, exc)

    # --- Environment override ---
    env_pem = os.environ.get(ENV_LICENSE_PUBLIC_KEY, "").strip()
    if env_pem:
        key = _load_pem(env_pem)
        if key is not None:
            keys[_ENV_KID] = key
            logger.debug("Loaded %s override: kid=%s", ENV_LICENSE_PUBLIC_KEY, _ENV_KID)

    if not keys:
        logger.warning(
            "No license public keys available; license verification will fail closed. "
            "Ensure public key PEM resources are bundled or set RHESIS_LICENSE_PUBLIC_KEY."
        )

    return keys


__all__ = ["get_public_keys"]

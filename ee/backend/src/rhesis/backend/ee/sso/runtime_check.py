"""Runtime precondition check for the SSO feature.

Imported lazily by :func:`rhesis.backend.ee.bootstrap` when registering
the SSO :class:`~rhesis.backend.app.features.Feature`. The function is
re-imported on every call so that test patches applied after module load
are reflected correctly.
"""

from __future__ import annotations


def sso_runtime_check() -> bool:
    """Return ``True`` iff the SSO encryption key is configured.

    Re-imports :func:`~rhesis.backend.app.utils.encryption.is_sso_encryption_available`
    on each invocation so that monkeypatching in tests works without
    needing to reach into registry internals.
    """
    from rhesis.backend.app.utils.encryption import is_sso_encryption_available

    return is_sso_encryption_available()

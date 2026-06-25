"""Fixtures for the EE RBAC test suite.

Ensures the capability catalog is populated before every RBAC test.
``auth/test_rbac.py`` calls ``reset_capabilities()`` in its teardown;
without re-registering here, ``get_all_capabilities()`` would return ``[]``
for the entire RBAC suite, causing all built-in-role permission checks to
silently pass (empty set always satisfies set-relation tests) or fail
(specific capability lookups return False because nothing is in the catalog).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _ensure_capabilities_registered():
    """Re-register the capability catalog from the real app before each test.

    Idempotent: ``register_capabilities`` replaces the cache, so calling it
    when the cache is already populated is harmless.
    """
    from rhesis.backend.app.auth.capabilities import register_capabilities
    from rhesis.backend.app.main import app

    register_capabilities(app)

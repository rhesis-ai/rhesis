"""Fixtures for the security test suite.

Ensures the capability catalog is populated before every security test.
``auth/test_rbac.py::TestCapabilities`` calls ``reset_capabilities()`` in its
teardown; without re-registering here, ``get_all_capabilities()`` would return
``[]`` for any security test that runs after that class, causing
``test_capability_catalog.py`` to see the full DB set as "extra" (catalog
drifted) even when the migration and routes are perfectly in sync.
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

"""Test fixtures for EE-package tests.

Why a session-scoped autouse fixture?
-------------------------------------
:class:`~rhesis.backend.app.features.FeatureRegistry` is process-global
state. A unit test elsewhere that calls :meth:`FeatureRegistry.reset` (for
isolation) will leave the registry empty, after which any SSO test that
calls ``check_sso_available()`` would see SSO as unregistered and
silently return ``False`` — masking real failures.

Re-running ``ee.bootstrap`` between modules cheaply restores the SSO
registration that the EE package would install at app startup. Tests
that need a *clean* registry (e.g. registry unit tests) still call
``FeatureRegistry.reset()`` explicitly; this fixture only ensures the
default state is "SSO is registered" rather than "registry is empty".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.features import FeatureName, FeatureRegistry


@pytest.fixture(autouse=True)
def _ensure_ee_sso_registered():
    """Register SSO before each EE test if it has been wiped.

    Re-runs the EE bootstrap when ``FeatureName.SSO`` is missing from the
    registry. Cheap (just a dict insert + ``app.include_router`` on a mock)
    and idempotent.
    """
    if FeatureName.SSO not in FeatureRegistry._features:
        from rhesis.backend.ee import bootstrap

        bootstrap(MagicMock())
    yield

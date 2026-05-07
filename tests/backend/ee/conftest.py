"""Test fixtures for EE-package tests.

Why a session-scoped autouse fixture?
-------------------------------------
:class:`~rhesis.backend.app.features.FeatureRegistry` and
:mod:`~rhesis.backend.app.auth.provider_hooks` are both process-global
state. A unit test elsewhere that calls :meth:`FeatureRegistry.reset`
(for isolation) leaves the registry empty, after which any EE test
would see its feature as unregistered and silently behave as if EE
were absent — masking real failures.

Re-running ``ee.bootstrap`` between modules cheaply restores both the
feature registry and the provider-enricher list to their startup
state. Tests that need a *clean* registry still call
``FeatureRegistry.reset()`` explicitly; this fixture only ensures the
default state is "EE features and enrichers are registered" rather
than "everything is empty".

The check is intentionally feature-agnostic — ``not _features`` rather
than ``FeatureName.SSO not in _features`` — so adding a second EE
feature requires no change here.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.auth.provider_hooks import reset_enrichers
from rhesis.backend.app.features import FeatureRegistry


@pytest.fixture(autouse=True)
def _ensure_ee_features_registered():
    """Re-bootstrap EE features when the registry has been wiped.

    Cheap: dict inserts plus ``app.include_router`` on a mock. The
    enricher list is reset first so re-running ``bootstrap`` does not
    leave stale callbacks behind from a previous run.
    """
    if not FeatureRegistry._features:
        from rhesis.backend.ee import bootstrap

        reset_enrichers()
        bootstrap(MagicMock())
    yield

"""Tests for :func:`~rhesis.backend.app.auth.feature_gates.require_feature`
and :func:`~rhesis.backend.app.auth.feature_gates.has_feature` under
the :class:`~rhesis.backend.ee.licensing.provider.SignedTokenLicenseProvider`.

Ensures that a route gated with ``require_feature`` returns 404 when the
org holds no valid license (non-enumeration guarantee). There is no
environment-based bypass: missing a license always denies, everywhere.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi import Depends

from rhesis.backend.app.auth.feature_gates import has_feature, require_feature
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.models.organization import Organization

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)

_ORG_UUID = UUID("aaaaaaaa-bbbb-cccc-dddd-000000000001")


def _build_app() -> tuple[FastAPI, dict]:
    """Build a minimal FastAPI app with a gated endpoint."""
    from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider

    mini_app = FastAPI()
    overrides: dict = {}

    @mini_app.get("/gated")
    def gated_endpoint(org: object = Depends(require_feature(FeatureName.SSO))):
        return {"ok": True}

    @mini_app.get("/flag")
    def flag_endpoint(available: bool = Depends(has_feature(FeatureName.SSO))):
        return {"available": available}

    return mini_app, overrides


@pytest.fixture
def gated_client():
    """TestClient for a minimal app with a gated route."""
    from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider

    mini_app, _ = _build_app()

    org_stub = MagicMock(spec=Organization)
    org_stub.id = _ORG_UUID
    org_stub.license = None

    db_stub = MagicMock()
    db_stub.query.return_value.filter.return_value.first.return_value = org_stub

    user_stub = MagicMock()
    user_stub.organization_id = _ORG_UUID

    mini_app.dependency_overrides[require_current_user_or_token] = lambda: user_stub
    mini_app.dependency_overrides[get_db_session] = lambda: db_stub

    FeatureRegistry.reset()
    FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
    FeatureRegistry.set_license_provider(SignedTokenLicenseProvider())

    yield TestClient(mini_app, raise_server_exceptions=True)

    FeatureRegistry.reset()


class TestRequireFeatureGate:
    def test_unlicensed_returns_404(self, gated_client):
        """require_feature raises 404 (not 403) when license is absent."""
        with patch.dict(os.environ, {"RHESIS_LICENSE": ""}):
            response = gated_client.get("/gated")
        assert response.status_code == 404

    def test_unregistered_feature_returns_404(self, gated_client):
        """Unregistered feature is indistinguishable from an unlicensed one."""
        FeatureRegistry.reset()  # wipe SSO registration
        with patch.dict(os.environ, {"RHESIS_LICENSE": ""}):
            response = gated_client.get("/gated")
        # Re-register so other tests see a clean state via the autouse fixture
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        assert response.status_code == 404

"""Integration tests for the ``GET /features`` endpoint."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.user_utils import require_current_user
from rhesis.backend.app.features import (
    Feature,
    FeatureName,
    FeatureRegistry,
)
from rhesis.backend.app.features_bootstrap import register_core_features
from rhesis.backend.app.main import app
from rhesis.backend.app.models.subscription import SubscriptionPlan


@pytest.fixture
def registered_sso():
    """Ensure SSO is registered for the duration of the test."""
    FeatureRegistry.reset()
    FeatureRegistry.register(
        Feature(
            name=FeatureName.SSO,
            display_name="Single Sign-On",
            min_plan=SubscriptionPlan.PREMIUM,
            description="Per-organization OIDC-based SSO.",
        )
    )
    yield
    FeatureRegistry.reset()
    register_core_features()


@pytest.fixture
def mock_current_user():
    """Override ``require_current_user`` with a mock user bound to an org."""
    mock_user = Mock()
    mock_user.organization = Mock()
    mock_user.organization.id = "00000000-0000-0000-0000-000000000000"

    def _override():
        return mock_user

    app.dependency_overrides[require_current_user] = _override
    yield mock_user
    app.dependency_overrides.clear()


class TestFeaturesEndpoint:
    def test_requires_authentication(self, client: TestClient, registered_sso):
        response = client.get("/features")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_license_info(
        self, client: TestClient, registered_sso, mock_current_user
    ):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "license" in body
        assert body["license"] == {"edition": "community", "licensed": False}

    def test_returns_enabled_list(
        self, client: TestClient, registered_sso, mock_current_user
    ):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["enabled"] == ["sso"]

    def test_omits_feature_when_runtime_check_fails(
        self, client: TestClient, mock_current_user
    ):
        FeatureRegistry.reset()
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["enabled"] == []
        finally:
            FeatureRegistry.reset()
            register_core_features()

    def test_omits_feature_when_license_denies(
        self, client: TestClient, mock_current_user
    ):
        class _Deny:
            def allows_feature(self, feature, org):
                return False

            def info(self):
                return {"edition": "community", "licensed": False}

        FeatureRegistry.reset()
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        FeatureRegistry.set_license_provider(_Deny())
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["enabled"] == []
        finally:
            FeatureRegistry.reset()
            register_core_features()

    def test_response_shape_is_stable(
        self, client: TestClient, registered_sso, mock_current_user
    ):
        response = client.get("/features")
        body = response.json()
        assert set(body.keys()) == {"license", "enabled"}
        assert set(body["license"].keys()) == {"edition", "licensed"}
        assert isinstance(body["enabled"], list)
        assert all(isinstance(name, str) for name in body["enabled"])

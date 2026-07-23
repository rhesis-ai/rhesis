"""Tests for the local-only platform sync feature.

The platform (remote) is fully mocked via ``PlatformClient`` so these tests are
offline and deterministic. Local upserts hit the real test database through the
``authenticated_client`` + ``test_db`` fixtures.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from rhesis.backend.app import models
from rhesis.backend.app.services.platform_sync import REGISTRY, resolve_order
from rhesis.backend.app.services.platform_sync.client import PlatformClient
from rhesis.backend.app.services.platform_sync.registry import SyncContext
from rhesis.sdk.clients.api import Endpoints

# ---------------------------------------------------------------------------
# Pure unit tests (no DB, no network)
# ---------------------------------------------------------------------------


class TestResolveOrder:
    def test_endpoints_pulls_projects_first(self):
        assert resolve_order(["endpoints"]) == ["projects", "endpoints"]

    def test_dedupes_and_preserves_dependency_order(self):
        order = resolve_order(["endpoints", "projects", "models"])
        assert order.index("projects") < order.index("endpoints")
        assert order.count("projects") == 1

    def test_unknown_resource_raises_422(self):
        with pytest.raises(HTTPException) as exc:
            resolve_order(["not_a_resource"])
        assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestModelHasKey:
    def test_empty_key_is_false(self):
        assert models.Model(key="").has_key is False

    def test_present_key_is_true(self):
        assert models.Model(key="sk-abc").has_key is True


class TestAccountSync:
    """Account access mirrors platform verification onto the local user."""

    def _ctx_with_user(self, *, is_verified: bool) -> tuple[SyncContext, MagicMock]:
        user = MagicMock()
        user.is_verified = is_verified
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        ctx = SyncContext(
            db=db,
            organization_id="00000000-0000-0000-0000-0000000000aa",
            user_id="11111111-1111-1111-1111-111111111111",
            client=None,
        )
        return ctx, user

    def test_elevates_when_platform_verified(self):
        ctx, user = self._ctx_with_user(is_verified=False)
        result = REGISTRY["account"].upsert(ctx, [{"is_verified": True}])
        assert user.is_verified is True
        assert result.updated == 1

    def test_does_not_downgrade(self):
        ctx, user = self._ctx_with_user(is_verified=True)
        result = REGISTRY["account"].upsert(ctx, [{"is_verified": False}])
        assert user.is_verified is True
        assert result.skipped == 1


# ---------------------------------------------------------------------------
# Platform mocking
# ---------------------------------------------------------------------------


def _install_fake_platform(monkeypatch, *, data: dict, email: str = "prod@example.com"):
    """Patch PlatformClient so the remote platform returns canned data."""

    def fake_introspect(self):
        return {
            "organization_id": "00000000-0000-0000-0000-0000000000aa",
            "user_email": email,
            "project_id": None,
        }

    def fake_list(self, endpoint, params=None):
        return list(data.get(endpoint, []))

    monkeypatch.setattr(PlatformClient, "introspect_token", fake_introspect)
    monkeypatch.setattr(PlatformClient, "list", fake_list)


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


class TestLocalOnlyGuard:
    def test_refuses_on_production(self, authenticated_client: TestClient, monkeypatch):
        class _ProdSettings:
            is_production = True
            is_google_cloud = False
            gcp_project = None
            google_cloud_project = None

        monkeypatch.setattr(
            "rhesis.backend.app.auth.local_only.get_application_settings",
            lambda: _ProdSettings(),
        )
        response = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": []}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_refuses_on_google_cloud(self, authenticated_client: TestClient, monkeypatch):
        class _CloudSettings:
            is_production = False
            is_google_cloud = True
            gcp_project = None
            google_cloud_project = None

        monkeypatch.setattr(
            "rhesis.backend.app.auth.local_only.get_application_settings",
            lambda: _CloudSettings(),
        )
        response = authenticated_client.get("/platform-sync/resources")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestResourcesEndpoint:
    def test_lists_resources_with_dependencies(self, authenticated_client: TestClient):
        response = authenticated_client.get("/platform-sync/resources")
        assert response.status_code == status.HTTP_200_OK
        by_key = {item["key"]: item for item in response.json()}
        assert "models" in by_key
        assert "endpoints" in by_key
        assert by_key["endpoints"]["dependencies"] == ["projects"]


class TestModelSync:
    def test_maps_provider_by_name_and_reports_key_gap(
        self, authenticated_client: TestClient, test_db, monkeypatch
    ):
        model_name = f"PSync OpenAI {uuid.uuid4().hex[:8]}"
        _install_fake_platform(
            monkeypatch,
            data={
                Endpoints.MODELS: [
                    {
                        "name": model_name,
                        "model_name": "gpt-4",
                        "model_type": "language",
                        "provider_type": {"type_value": "openai"},
                        "status": {"name": "Available"},
                    }
                ]
            },
        )
        response = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": ["models"]}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        result = next(r for r in body["results"] if r["resource"] == "models")
        assert result["created"] == 1
        assert any(g["field"] == "key" and g["name"] == model_name for g in body["gaps"])

        created = test_db.query(models.Model).filter(models.Model.name == model_name).first()
        assert created is not None
        assert created.key == ""  # secret left blank
        assert created.is_protected is False
        assert created.provider_type is not None
        assert created.provider_type.type_value == "openai"

    def test_system_models_stored_with_pasted_key(
        self, authenticated_client: TestClient, test_db, monkeypatch
    ):
        rhesis_name = f"PSync Rhesis Default {uuid.uuid4().hex[:8]}"
        poly_name = f"PSync Polyphemus {uuid.uuid4().hex[:8]}"
        data = {
            Endpoints.MODELS: [
                {
                    "name": rhesis_name,
                    "model_name": "default",
                    "model_type": "language",
                    "provider_type": {"type_value": "rhesis"},
                    "status": {"name": "Available"},
                },
                {
                    "name": poly_name,
                    "model_name": "default",
                    "model_type": "language",
                    "provider_type": {"type_value": "polyphemus"},
                    "status": {"name": "Available"},
                },
            ]
        }
        _install_fake_platform(monkeypatch, data=data)
        response = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-secret", "resources": ["models"]}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        # System providers carry the pasted key, so they produce no key gap.
        assert not any(
            g["name"].startswith(rhesis_name) or g["name"].startswith(poly_name)
            for g in body["gaps"]
        )

        for original in (rhesis_name, poly_name):
            synced = (
                test_db.query(models.Model)
                .filter(models.Model.name == f"{original} (synced from api.rhesis.ai)")
                .first()
            )
            assert synced is not None, f"expected a synced row for {original}"
            assert synced.key == "rh-secret"  # pasted key stored (write-only)
            assert synced.is_protected is False
            # The original (keyless) model is left untouched — added new, not overwritten.
            assert test_db.query(models.Model).filter(models.Model.name == original).first() is None

        # Re-syncing from the same platform skips (idempotent per platform).
        second = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-secret", "resources": ["models"]}
        ).json()
        second_models = next(r for r in second["results"] if r["resource"] == "models")
        assert second_models["created"] == 0
        assert second_models["skipped"] == 2

    def test_idempotent_rerun_skips(self, authenticated_client: TestClient, test_db, monkeypatch):
        model_name = f"PSync Idem {uuid.uuid4().hex[:8]}"
        data = {
            Endpoints.MODELS: [
                {
                    "name": model_name,
                    "model_name": "gpt-4",
                    "model_type": "language",
                    "provider_type": {"type_value": "openai"},
                    "status": {"name": "Available"},
                }
            ]
        }
        _install_fake_platform(monkeypatch, data=data)

        first = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": ["models"]}
        ).json()
        second = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": ["models"]}
        ).json()

        first_models = next(r for r in first["results"] if r["resource"] == "models")
        second_models = next(r for r in second["results"] if r["resource"] == "models")
        assert first_models["created"] == 1
        assert second_models["created"] == 0
        assert second_models["skipped"] == 1

        rows = test_db.query(models.Model).filter(models.Model.name == model_name).all()
        assert len(rows) == 1

    def test_unknown_resource_returns_422(self, authenticated_client: TestClient, monkeypatch):
        _install_fake_platform(monkeypatch, data={})
        response = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": ["bogus"]}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestEndpointSync:
    def test_creates_endpoint_resolves_project_and_reports_auth_gap(
        self, authenticated_client: TestClient, test_db, monkeypatch
    ):
        project_name = f"PSync Project {uuid.uuid4().hex[:8]}"
        endpoint_name = f"PSync Endpoint {uuid.uuid4().hex[:8]}"
        _install_fake_platform(
            monkeypatch,
            data={
                Endpoints.PROJECTS: [
                    {"id": "aaaa0000-0000-0000-0000-000000000001", "name": project_name}
                ],
                Endpoints.ENDPOINTS: [
                    {
                        "id": "bbbb0000-0000-0000-0000-000000000001",
                        "name": endpoint_name,
                        "connection_type": "REST",
                        "url": "https://example.test/chat",
                        "environment": "development",
                        "auth_type": "bearer_token",
                        "has_auth_token": True,
                        "project": {"name": project_name},
                        "status": {"name": "Active"},
                    }
                ],
            },
        )
        response = authenticated_client.post(
            "/platform-sync", json={"api_key": "rh-x", "resources": ["endpoints"]}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        endpoints_result = next(r for r in body["results"] if r["resource"] == "endpoints")
        assert endpoints_result["created"] == 1
        assert any(g["field"] == "auth_token" and g["name"] == endpoint_name for g in body["gaps"])

        project = test_db.query(models.Project).filter(models.Project.name == project_name).first()
        assert project is not None
        created = (
            test_db.query(models.Endpoint).filter(models.Endpoint.name == endpoint_name).first()
        )
        assert created is not None
        assert created.project_id == project.id
        assert created.auth_token is None  # secret left blank

        membership = (
            test_db.query(models.ProjectMembership)
            .filter(models.ProjectMembership.project_id == project.id)
            .first()
        )
        assert membership is not None

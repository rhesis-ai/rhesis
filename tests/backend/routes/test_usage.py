"""Integration tests for the ``GET /usage`` endpoint.

Unlike ``GET /features`` (which only touches in-memory registries),
``GET /usage`` queries the real `usage` table plus live stock-resource
counts, so these tests use ``authenticated_client`` (a real DB-backed
session under savepoint isolation) rather than mocked dependencies.
"""

from __future__ import annotations

from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.services.usage import increment_usage


class TestUsageEndpoint:
    def test_requires_authentication(self, client: TestClient):
        response = client.get("/usage")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_200_for_authenticated_user(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        assert response.status_code == status.HTTP_200_OK

    def test_response_shape_is_stable(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        body = response.json()

        assert set(body.keys()) == {"resources", "edition"}
        assert isinstance(body["resources"], dict)
        assert isinstance(body["edition"], str)

    def test_includes_every_quota_resource(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        body = response.json()

        assert set(body["resources"].keys()) == {r.value for r in QuotaResource}

    def test_each_resource_item_shape(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        body = response.json()

        for item in body["resources"].values():
            assert set(item.keys()) == {"used", "limit", "period_start", "period_end", "kind"}
            assert isinstance(item["used"], int)
            assert item["kind"] in ("flow", "stock")

    def test_kind_matches_stock_vs_flow_resource(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        body = response.json()

        stock_resources = {
            QuotaResource.SEATS.value,
            QuotaResource.PROJECTS.value,
            QuotaResource.ENDPOINTS.value,
        }
        for resource_value, item in body["resources"].items():
            expected_kind = "stock" if resource_value in stock_resources else "flow"
            assert item["kind"] == expected_kind

    def test_reflects_accrued_flow_usage(
        self, authenticated_client: TestClient, test_db, test_org_id
    ):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 7)

        response = authenticated_client.get("/usage")
        body = response.json()

        assert body["resources"][QuotaResource.TEST_EXECUTIONS.value]["used"] == 7

    def test_reflects_live_stock_count(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage")
        body = response.json()

        assert body["resources"][QuotaResource.SEATS.value]["used"] >= 1

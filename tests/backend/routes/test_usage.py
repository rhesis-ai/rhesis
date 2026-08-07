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


class TestUsagePeriodFilter:
    def test_defaults_to_current_period_when_omitted(self, authenticated_client: TestClient):
        default_response = authenticated_client.get("/usage")
        explicit_response = authenticated_client.get(
            f"/usage?period={default_response.json()['resources'][QuotaResource.SEATS.value]['period_start']}"
        )

        assert explicit_response.status_code == status.HTTP_200_OK
        assert (
            explicit_response.json()["resources"].keys()
            == default_response.json()["resources"].keys()
        )

    def test_still_includes_stock_resources_for_a_past_period(
        self, authenticated_client: TestClient
    ):
        response = authenticated_client.get("/usage?period=2026-01-01")
        body = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert body["resources"][QuotaResource.SEATS.value]["used"] >= 1

    def test_rejects_a_period_that_is_not_the_first_of_the_month(
        self, authenticated_client: TestClient
    ):
        response = authenticated_client.get("/usage?period=2026-01-15")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_a_period_in_the_future(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage?period=2099-01-01")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestUsageHistoryEndpoint:
    def test_requires_authentication(self, client: TestClient):
        response = client.get("/usage/history")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_200_for_authenticated_user(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history")
        assert response.status_code == status.HTTP_200_OK

    def test_response_shape_is_stable(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history")
        body = response.json()

        assert set(body.keys()) == {"resources"}
        assert isinstance(body["resources"], dict)

    def test_excludes_stock_resources(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history")
        body = response.json()

        stock_resources = {
            QuotaResource.SEATS.value,
            QuotaResource.PROJECTS.value,
            QuotaResource.ENDPOINTS.value,
        }
        assert stock_resources.isdisjoint(body["resources"].keys())

    def test_defaults_to_six_months(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history")
        body = response.json()

        assert len(body["resources"][QuotaResource.TRACING_SPANS.value]) == 6

    def test_months_param_controls_point_count(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history?months=3")
        body = response.json()

        assert len(body["resources"][QuotaResource.TRACING_SPANS.value]) == 3

    def test_rejects_months_outside_the_allowed_range(self, authenticated_client: TestClient):
        too_low = authenticated_client.get("/usage/history?months=0")
        too_high = authenticated_client.get("/usage/history?months=25")

        assert too_low.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert too_high.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_each_point_shape(self, authenticated_client: TestClient):
        response = authenticated_client.get("/usage/history?months=2")
        body = response.json()

        for points in body["resources"].values():
            for point in points:
                assert set(point.keys()) == {"period_start", "used"}
                assert isinstance(point["used"], int)

    def test_reflects_accrued_usage_at_the_latest_point(
        self, authenticated_client: TestClient, test_db, test_org_id
    ):
        increment_usage(test_db, test_org_id, QuotaResource.MODEL_TOKENS, 999)

        response = authenticated_client.get("/usage/history?months=2")
        body = response.json()

        points = body["resources"][QuotaResource.MODEL_TOKENS.value]
        assert points[-1]["used"] == 999

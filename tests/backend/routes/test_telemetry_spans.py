"""Tests for GET /telemetry/spans and GET /telemetry/spans/facets.

Filter and sort behaviour is covered in tests/backend/crud/test_span_list.py; these
check the HTTP layer: params, validation, auth and tenant isolation.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.backend.fixtures.rls import scope_to_org, scope_to_project
from tests.backend.routes.fixtures.data_factories import TraceDataFactory


def ingest(client: TestClient, project_id: str, **overrides) -> dict:
    span = TraceDataFactory.sample_data(project_id=project_id)
    span.update(overrides)
    response = client.post("/telemetry/traces", json={"spans": [span]})
    assert response.status_code == status.HTTP_200_OK, response.text
    return span


@pytest.mark.integration
class TestListSpans:
    def test_response_shape(self, authenticated_client: TestClient, db_project):
        span = ingest(authenticated_client, str(db_project.id))

        response = authenticated_client.get(f"/telemetry/spans?project_id={db_project.id}")

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert (data["limit"], data["offset"]) == (100, 0)
        row = next(s for s in data["spans"] if s["span_id"] == span["span_id"])
        assert row["trace_id"] == span["trace_id"]
        assert row["is_root"] is True
        assert row["trace_name"] == span["span_name"]
        assert {"span_type", "cost_usd", "total_tokens", "model", "provider"} <= row.keys()

    def test_repeatable_params(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        a = ingest(authenticated_client, project_id, span_name="function.alpha")
        b = ingest(authenticated_client, project_id, span_name="function.beta")
        ingest(authenticated_client, project_id, span_name="function.gamma")

        response = authenticated_client.get(
            "/telemetry/spans",
            params={
                "project_id": project_id,
                "span_name": ["function.alpha", "function.beta"],
            },
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert {s["span_id"] for s in response.json()["spans"]} == {a["span_id"], b["span_id"]}

    def test_sort_and_page(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        for _ in range(3):
            ingest(authenticated_client, project_id)

        response = authenticated_client.get(
            "/telemetry/spans",
            params={"project_id": project_id, "sort_by": "duration_ms", "limit": 2},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert len(data["spans"]) == 2 and data["total"] >= 3

    @pytest.mark.parametrize(
        "params",
        [
            {"sort_by": "attributes"},
            {"test_run_id": "not-a-uuid"},
            {"test_result_id": "nope"},
        ],
    )
    def test_bad_params_are_a_400(self, authenticated_client: TestClient, db_project, params):
        response = authenticated_client.get(
            "/telemetry/spans", params={"project_id": str(db_project.id), **params}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    def test_bad_sort_order_is_a_422(self, authenticated_client: TestClient, db_project):
        response = authenticated_client.get(
            "/telemetry/spans", params={"project_id": str(db_project.id), "sort_order": "up"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_requires_auth(self, client: TestClient, db_project):
        for path in ("/telemetry/spans", "/telemetry/spans/facets"):
            response = client.get(f"{path}?project_id={db_project.id}")
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ]


@pytest.mark.integration
class TestSpanFacets:
    def test_facets(self, authenticated_client: TestClient, db_project):
        project_id = str(db_project.id)
        ingest(authenticated_client, project_id, span_name="function.facet_me")

        response = authenticated_client.get(
            "/telemetry/spans/facets", params={"project_id": project_id}
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        data = response.json()
        assert {"value": "function.facet_me", "count": 1} in data["span_names"]
        assert data["span_types"] and data["span_names_truncated"] is False
        assert isinstance(data["models"], list)

    def test_name_limit_is_bounded(self, authenticated_client: TestClient, db_project):
        response = authenticated_client.get(
            "/telemetry/spans/facets",
            params={"project_id": str(db_project.id), "name_limit": 10_000},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestSpanTenantIsolation:
    @staticmethod
    def _org_client(test_db, client: TestClient, label: str):
        """Fresh org + owner + project + client; see test_telemetry_query.py."""
        from rhesis.backend.app.crud.project import create_project
        from tests.backend.fixtures.test_setup import create_test_organization_and_user

        suffix = uuid.uuid4()
        org, user, token = create_test_organization_and_user(
            test_db,
            f"Org {label} {suffix}",
            f"user-{label}-{suffix}@test.com".lower(),
            f"User {label}",
        )
        project = create_project(
            test_db,
            {"name": f"Project {label} {suffix}", "description": "Test project"},
            organization_id=str(org.id),
            user_id=str(user.id),
        )
        org_client = TestClient(client.app)
        org_client.headers = {"Authorization": f"Bearer {token.token}"}
        return org_client, str(project.id), str(org.id)

    @staticmethod
    def _acting_as(test_db, org_id, project_id):
        scope_to_org(test_db, org_id)
        scope_to_project(test_db, project_id)

    def test_only_own_organizations_spans(self, test_db, client: TestClient):
        client_a, project_a, org_a = self._org_client(test_db, client, "A Spans")
        client_b, project_b, org_b = self._org_client(test_db, client, "B Spans")

        self._acting_as(test_db, org_a, project_a)
        span_a = ingest(client_a, project_a)
        self._acting_as(test_db, org_b, project_b)
        span_b = ingest(client_b, project_b, span_name="function.only_in_b")

        self._acting_as(test_db, org_a, project_a)
        response = client_a.get(f"/telemetry/spans?project_id={project_a}")
        assert response.status_code == 200, response.text
        seen = {s["span_id"] for s in response.json()["spans"]}
        assert span_a["span_id"] in seen and span_b["span_id"] not in seen

        # Asking for B's project from org A must not return B's spans, whatever the status.
        self._acting_as(test_db, org_a, project_b)
        response = client_a.get(f"/telemetry/spans?project_id={project_b}")
        if response.status_code == 200:
            assert span_b["span_id"] not in {s["span_id"] for s in response.json()["spans"]}
        response = client_a.get(f"/telemetry/spans/facets?project_id={project_b}")
        if response.status_code == 200:
            names = {f["value"] for f in response.json()["span_names"]}
            assert "function.only_in_b" not in names

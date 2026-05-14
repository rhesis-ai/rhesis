"""Routes tests for the project-scoped parameter management endpoints.

Phase 1 surface (this module): ``GET`` / ``PUT`` of the parameter
schema. Round-trip and tenant-isolation are the two invariants we lock
here: anything else (label endpoints, the resolver, experiment CRUD)
ships in later phases against the same router.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient


def _project_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/schema"


def _sample_schema_payload() -> dict:
    """A representative non-trivial schema covering each value type."""
    return {
        "fields": [
            {
                "name": "system_prompt",
                "type": "text",
                "required": False,
                "default": {"type": "text", "value": "Be helpful."},
                "display_order": 0,
            },
            {
                "name": "model",
                "type": "string",
                "required": False,
                "display_order": 1,
            },
            {
                "name": "temperature",
                "type": "number",
                "required": False,
                "default": {"type": "number", "value": 0.7},
                "display_order": 2,
            },
            {
                "name": "max_tokens",
                "type": "integer",
                "required": False,
                "default": {"type": "integer", "value": 1024},
                "display_order": 3,
            },
            {
                "name": "stream",
                "type": "boolean",
                "required": False,
                "default": {"type": "boolean", "value": True},
                "display_order": 4,
            },
            {
                "name": "output_mode",
                "type": "enum",
                "required": False,
                "options": ["text", "json"],
                "default": {"type": "enum", "value": "text"},
                "display_order": 5,
            },
        ]
    }


@pytest.mark.integration
class TestParametersSchemaRoundTrip:
    """The schema PUT/GET pair is the single editor-server contract."""

    def test_get_default_empty_schema(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.get(_project_url(db_project.id))

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # A freshly created project carries the column default — no fields,
        # no surprise extras. Same shape as a deliberately cleared schema.
        assert body == {"fields": []}

    def test_put_replaces_schema_atomically(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        payload = _sample_schema_payload()

        put_resp = authenticated_client.put(
            _project_url(db_project.id), json=payload
        )
        assert put_resp.status_code == status.HTTP_200_OK
        put_body = put_resp.json()
        assert [f["name"] for f in put_body["fields"]] == [
            f["name"] for f in payload["fields"]
        ]
        # Round-trip the typed defaults back as discriminator dicts.
        temperature_field = next(
            f for f in put_body["fields"] if f["name"] == "temperature"
        )
        assert temperature_field["default"] == {"type": "number", "value": 0.7}

        get_resp = authenticated_client.get(_project_url(db_project.id))
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json() == put_body

    def test_put_overwrites_previous_schema(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # First PUT: full schema.
        first = authenticated_client.put(
            _project_url(db_project.id), json=_sample_schema_payload()
        )
        assert first.status_code == status.HTTP_200_OK
        assert len(first.json()["fields"]) > 1

        # Second PUT: replace with a much smaller schema. The previous
        # fields must not linger — this is the whole point of "single
        # PUT replaces the whole schema".
        replacement = {
            "fields": [
                {"name": "only_field", "type": "string", "required": True}
            ]
        }
        second = authenticated_client.put(
            _project_url(db_project.id), json=replacement
        )
        assert second.status_code == status.HTTP_200_OK
        body = second.json()
        assert [f["name"] for f in body["fields"]] == ["only_field"]
        assert body["fields"][0]["required"] is True

    def test_put_rejects_duplicate_field_names(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        payload = {
            "fields": [
                {"name": "dup", "type": "string"},
                {"name": "dup", "type": "integer"},
            ]
        }
        response = authenticated_client.put(
            _project_url(db_project.id), json=payload
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_put_rejects_enum_without_options(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        payload = {"fields": [{"name": "broken_enum", "type": "enum"}]}
        response = authenticated_client.put(
            _project_url(db_project.id), json=payload
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_put_rejects_non_snake_case_name(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        payload = {"fields": [{"name": "NotSnakeCase", "type": "string"}]}
        response = authenticated_client.put(
            _project_url(db_project.id), json=payload
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestParametersSchemaTenantIsolation:
    """Cross-tenant safety: an unknown project id surfaces as 404."""

    def test_unknown_project_returns_404(
        self, authenticated_client: TestClient
    ) -> None:
        # A random UUID is unreachable from this org — we expect 404
        # (not 403) so existence isn't leaked across projects.
        response = authenticated_client.get(_project_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_put_unknown_project_returns_404(
        self, authenticated_client: TestClient
    ) -> None:
        response = authenticated_client.put(
            _project_url(uuid.uuid4()),
            json={"fields": []},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

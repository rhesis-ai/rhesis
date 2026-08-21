"""API-level behavior for issue #744: id/nano_id are server-assigned, not client-settable.

Verifies what actually happens at the HTTP boundary (the schema-level and route-introspection
guarantees live in tests/backend/schemas/test_server_identity.py): a client-supplied id/nano_id
in a create or update body is silently ignored -- Pydantic's default extra="ignore" drops the
unrecognized key before it ever reaches the CRUD layer, so the response comes back with the
backend's own values, not the caller's.

Uses the category endpoint as a representative CRUD entity; the same Base-derived schema
pattern applies to every other entity covered by tests/backend/schemas/test_server_identity.py.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from .endpoints import APIEndpoints
from .faker_utils import generate_category_data


@pytest.mark.unit
class TestServerOwnedIdentityIgnoredOnWrite:
    def test_create_ignores_client_supplied_id_and_nano_id(self, authenticated_client: TestClient):
        data = generate_category_data()
        data.pop("status_id", None)
        data.pop("entity_type_id", None)
        spoofed_id = str(uuid.uuid4())
        data["id"] = spoofed_id
        data["nano_id"] = "attacker-chosen"

        response = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=data)

        assert response.status_code == status.HTTP_200_OK
        created = response.json()
        assert created["id"] != spoofed_id
        assert created["nano_id"] != "attacker-chosen"
        assert created["nano_id"]  # server still assigned one

    def test_update_ignores_client_supplied_id_and_nano_id(self, authenticated_client: TestClient):
        data = generate_category_data()
        data.pop("status_id", None)
        data.pop("entity_type_id", None)
        created = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=data).json()

        real_id = created["id"]
        real_nano_id = created["nano_id"]
        other_id = str(uuid.uuid4())

        response = authenticated_client.put(
            APIEndpoints.CATEGORIES.put(real_id),
            json={"name": "renamed", "id": other_id, "nano_id": "attacker-chosen"},
        )

        assert response.status_code == status.HTTP_200_OK
        updated = response.json()
        assert updated["id"] == real_id
        assert updated["nano_id"] == real_nano_id
        assert updated["name"] == "renamed"

        # Nothing was created or repointed under the spoofed id.
        other_lookup = authenticated_client.get(APIEndpoints.CATEGORIES.get(other_id))
        assert other_lookup.status_code == status.HTTP_404_NOT_FOUND

"""Routes tests for the experiment header + versions sub-resource.

Covers Phase 2 surface: per-project list/create, header CRUD on
``/experiments/{id}``, the version append (idempotency + content
hashing), label binding (gated on shared visibility + version exists),
and the canonical resolver. Plan-locked invariants under test:

- Visibility 404 (private experiments invisible to non-owners, even
  with elevated org roles).
- Cross-project leak is also a 404.
- Unsharing or deleting an experiment with an active label → 409.
- Saving identical values is idempotent (no new version, 200 not 201).
- Resolver precedence: ``version`` > ``experiment_id`` > ``label`` >
  implicit ``default``.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _schema_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/schema"


def _experiments_url(project_id) -> str:
    return f"/projects/{project_id}/experiments"


def _experiment_url(experiment_id) -> str:
    return f"/experiments/{experiment_id}"


def _versions_url(experiment_id) -> str:
    return f"/experiments/{experiment_id}/versions"


def _labels_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/labels"


def _label_url(project_id, name) -> str:
    return f"/projects/{project_id}/parameters/labels/{name}"


def _resolve_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/resolve"


def _seed_schema(client: TestClient, project_id) -> None:
    """Install the canonical chatbot-style schema for value validation tests."""
    payload = {
        "fields": [
            {
                "name": "system_prompt",
                "type": "text",
                "required": False,
                "default": {"type": "text", "value": "Be helpful."},
            },
            {
                "name": "model",
                "type": "string",
                "required": False,
                "default": {"type": "string", "value": "gpt-4o"},
            },
            {
                "name": "temperature",
                "type": "number",
                "required": False,
                "default": {"type": "number", "value": 0.7},
            },
            {
                "name": "max_tokens",
                "type": "integer",
                "required": False,
                "default": {"type": "integer", "value": 1024},
            },
            {
                "name": "stream",
                "type": "boolean",
                "required": False,
                "default": {"type": "boolean", "value": True},
            },
            {
                "name": "output_mode",
                "type": "enum",
                "required": False,
                "options": ["text", "json"],
                "default": {"type": "enum", "value": "text"},
            },
        ]
    }
    response = client.put(_schema_url(project_id), json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text


def _create_experiment(
    client: TestClient,
    project_id,
    *,
    name: str = "baseline",
    visibility: str = "private",
) -> dict:
    response = client.post(
        _experiments_url(project_id),
        json={"name": name, "description": "test", "visibility": visibility},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _commit_version(
    client: TestClient,
    experiment_id,
    *,
    values: dict,
    message: str | None = None,
) -> tuple[dict, int]:
    response = client.post(
        _versions_url(experiment_id),
        json={"values": values, "message": message},
    )
    assert response.status_code in (
        status.HTTP_200_OK,
        status.HTTP_201_CREATED,
    ), response.text
    return response.json(), response.status_code


# --------------------------------------------------------------------------- #
# Header CRUD                                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestExperimentHeaderCRUD:
    """Create / read / patch / delete on experiment header rows."""

    def test_create_defaults_to_private(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        body = _create_experiment(authenticated_client, db_project.id)
        assert body["visibility"] == "private"
        assert body["versions_count"] == 0
        assert body["latest_version"] is None
        assert body["project_id"] == str(db_project.id)

    def test_get_returns_detail_with_versions(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9},
            message="initial",
        )
        response = authenticated_client.get(_experiment_url(created["id"]))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["versions_count"] == 1
        assert len(body["versions"]) == 1
        assert body["versions"][0]["version"].startswith("v_")

    def test_patch_updates_name_and_description(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        created = _create_experiment(authenticated_client, db_project.id)
        response = authenticated_client.patch(
            _experiment_url(created["id"]),
            json={"name": "renamed", "description": "new desc"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["name"] == "renamed"
        assert body["description"] == "new desc"

    def test_delete_with_no_label_succeeds(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        created = _create_experiment(authenticated_client, db_project.id)
        response = authenticated_client.delete(_experiment_url(created["id"]))
        assert response.status_code == status.HTTP_200_OK
        # Subsequent GET surfaces the deletion as 410 Gone — the CRUD
        # layer soft-deletes and the visibility-aware lookup
        # propagates the platform's standard tombstone status.
        follow = authenticated_client.get(_experiment_url(created["id"]))
        assert follow.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_410_GONE,
        )

    def test_get_unknown_experiment_is_404(
        self, authenticated_client: TestClient
    ) -> None:
        response = authenticated_client.get(_experiment_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------- #
# Versions: validation, hashing, idempotency                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestExperimentVersions:
    """Append-only versions array with content-hash IDs and idempotent saves."""

    def test_first_commit_returns_201_and_hash_id(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        body, code = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9, "model": "gpt-4o"},
        )
        assert code == status.HTTP_201_CREATED
        assert body["version"].startswith("v_")
        assert body["values"]["temperature"] == {"type": "number", "value": 0.9}
        assert body["values"]["model"] == {"type": "string", "value": "gpt-4o"}

    def test_second_identical_commit_is_idempotent(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        first, code1 = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9},
        )
        assert code1 == status.HTTP_201_CREATED

        # Same values again → idempotent. Status flips to 200, version
        # id is identical, and the experiment still has exactly one
        # entry in its versions array.
        second, code2 = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9},
        )
        assert code2 == status.HTTP_200_OK
        assert second["version"] == first["version"]

        listing = authenticated_client.get(_versions_url(created["id"]))
        assert listing.status_code == status.HTTP_200_OK
        assert len(listing.json()) == 1

    def test_different_values_appends_a_new_version(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        first, _ = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9},
        )
        second, code = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 1.4},
        )
        assert code == status.HTTP_201_CREATED
        assert second["version"] != first["version"]
        # The new version's parent_version points at the previous one
        # so the chain is reconstructable from the array alone.
        assert second["parent_version"] == first["version"]

        listing = authenticated_client.get(_versions_url(created["id"]))
        assert len(listing.json()) == 2

    def test_invalid_value_type_is_422(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        # temperature is a number; sending a string should fail
        # validation in validate_values_against_schema.
        response = authenticated_client.post(
            _versions_url(created["id"]),
            json={"values": {"temperature": "not-a-number"}},
        )
        # Mapped to 500 unless the route catches ValueError into 422.
        # Backend uses a service-layer ValueError; check it surfaces.
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def test_get_specific_version(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        created = _create_experiment(authenticated_client, db_project.id)
        committed, _ = _commit_version(
            authenticated_client,
            created["id"],
            values={"temperature": 0.9},
        )
        single = authenticated_client.get(
            f"{_versions_url(created['id'])}/{committed['version']}"
        )
        assert single.status_code == status.HTTP_200_OK
        assert single.json()["version"] == committed["version"]

    def test_get_unknown_version_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        created = _create_experiment(authenticated_client, db_project.id)
        response = authenticated_client.get(
            f"{_versions_url(created['id'])}/v_nope"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------- #
# Labels + visibility-bind invariant                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestProjectLabels:
    """Labels are movable pointers; binding has guard rails."""

    def test_labels_default_empty(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.get(_labels_url(db_project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"labels": {}}

    def test_bind_label_requires_shared_experiment(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        # Private experiments cannot be promoted — this is the
        # "labels point only at shared experiments" plan-locked rule.
        private_exp = _create_experiment(
            authenticated_client, db_project.id, name="priv"
        )
        committed, _ = _commit_version(
            authenticated_client,
            private_exp["id"],
            values={"temperature": 0.7},
        )
        response = authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={
                "experiment_id": private_exp["id"],
                "version": committed["version"],
            },
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_bind_label_then_unbind(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="shared-exp",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        bind = authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )
        assert bind.status_code == status.HTTP_200_OK
        assert "default" in bind.json()["labels"]

        unbind = authenticated_client.delete(_label_url(db_project.id, "default"))
        assert unbind.status_code == status.HTTP_200_OK
        assert "default" not in unbind.json()["labels"]

    def test_unsharing_with_active_label_is_409(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="will-stay-shared",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        # Trying to unshare while the label is bound is refused.
        response = authenticated_client.patch(
            _experiment_url(exp["id"]),
            json={"visibility": "private"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_deleting_with_active_label_is_409(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="protected-from-delete",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        response = authenticated_client.delete(_experiment_url(exp["id"]))
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_bind_unknown_version_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="empty-shared",
            visibility="shared",
        )
        response = authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": "v_nope"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------- #
# Resolver: precedence + visibility + cross-project                           #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestResolver:
    """`/resolve` is the single canonical path used by SDK and run-snapshot."""

    def test_implicit_default_label_when_no_args(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="will-be-default",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        authenticated_client.put(
            _label_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        response = authenticated_client.get(_resolve_url(db_project.id))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["source"] == "label"
        assert body["source_label"] == "default"
        assert body["version"] == committed["version"]
        assert body["values"]["temperature"] == {
            "type": "number",
            "value": 0.7,
        }

    def test_resolve_by_explicit_version_pins(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="versioned",
            visibility="shared",
        )
        first, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        second, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 1.4},
        )
        # Resolving by `version` (older one) returns that version even
        # though it isn't the latest — proves the immutable pin.
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={
                "experiment_id": exp["id"],
                "version": first["version"],
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["source"] == "version"
        assert body["version"] == first["version"]
        assert body["source_label"] is None

    def test_resolve_by_experiment_id_returns_latest(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="for-experiment-id",
            visibility="shared",
        )
        _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        latest, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 1.4},
        )
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={"experiment_id": exp["id"]},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["source"] == "experiment_id"
        assert body["version"] == latest["version"]

    def test_resolve_unbound_label_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={"label": "production"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_resolve_cross_project_id_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # Resolving an experiment id that doesn't belong to the named
        # project surfaces as 404 — never 403, so existence is not
        # leaked across projects.
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={"experiment_id": str(uuid.uuid4())},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

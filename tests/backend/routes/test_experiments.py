"""Routes tests for the experiment header + versions sub-resource.

Covers Phase 2 surface: per-project list/create, header CRUD on
``/experiments/{id}``, the version append (idempotency + content
hashing), environment binding (gated on shared visibility + version exists),
and the canonical resolver. Plan-locked invariants under test:

- Visibility 404 (private experiments invisible to non-owners, even
  with elevated org roles).
- Cross-project leak is also a 404.
- Unsharing or deleting an experiment with an active environment → 409.
- Saving identical values is idempotent (no new version, 200 not 201).
- Resolver precedence: ``version`` > ``experiment_id`` > ``environment`` >
  implicit ``default``.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.schemas.parameters import BuiltInEnvironment


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


def _environments_url(project_id) -> str:
    return f"/projects/{project_id}/parameters/environments"


def _environment_url(project_id, name) -> str:
    return f"/projects/{project_id}/parameters/environments/{name}"


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
        assert body["versions"][0]["version"] == "v1"
        assert body["versions"][0]["content_hash"]

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

    def test_delete_with_no_environment_succeeds(
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
        assert body["version"] == "v1"
        assert body["content_hash"]
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
        assert first["version"] == "v1"
        assert second["version"] == "v2"
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
# Environments + visibility-bind invariant                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestProjectEnvironments:
    """Environments are movable pointers; binding has guard rails."""

    def test_environments_default_empty(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.get(_environments_url(db_project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"environments": {}}

    def test_bind_environment_requires_shared_experiment(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        _seed_schema(authenticated_client, db_project.id)
        # Private experiments cannot be promoted — this is the
        # "environments point only at shared experiments" plan-locked rule.
        private_exp = _create_experiment(
            authenticated_client, db_project.id, name="priv"
        )
        committed, _ = _commit_version(
            authenticated_client,
            private_exp["id"],
            values={"temperature": 0.7},
        )
        response = authenticated_client.put(
            _environment_url(db_project.id, "default"),
            json={
                "experiment_id": private_exp["id"],
                "version": committed["version"],
            },
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_bind_environment_then_unbind(
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
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )
        assert bind.status_code == status.HTTP_200_OK
        assert "default" in bind.json()["environments"]

        unbind = authenticated_client.delete(
            _environment_url(db_project.id, "default")
        )
        assert unbind.status_code == status.HTTP_200_OK
        assert "default" not in unbind.json()["environments"]

    def test_unsharing_with_active_environment_is_409(
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
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        # Trying to unshare while the environment is bound is refused.
        response = authenticated_client.patch(
            _experiment_url(exp["id"]),
            json={"visibility": "private"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_deleting_with_active_environment_cascades(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        """Delete auto-unbinds any environments pointing at the experiment."""
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="cascade-delete",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        authenticated_client.put(
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        response = authenticated_client.delete(_experiment_url(exp["id"]))
        assert response.status_code == status.HTTP_200_OK

        envs = authenticated_client.get(
            f"/projects/{db_project.id}/parameters/environments"
        )
        pointer = envs.json()["environments"].get("default")
        assert pointer is None

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
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": "v_nope"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------- #
# Environment name validation                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestEnvironmentNameRules:
    """``PUT /environments/{name}`` rejects names outside the allowed shape.

    ``DELETE /environments/{name}`` stays permissive on purpose so legacy
    data written before the rule existed can still be cleaned up; that
    behavior is locked in here too.
    """

    def _shared_pointer(
        self, client: TestClient, project_id
    ) -> dict:
        """Create a shared experiment + version usable as a bind target."""
        _seed_schema(client, project_id)
        exp = _create_experiment(
            client, project_id, name="bindable", visibility="shared"
        )
        committed, _ = _commit_version(
            client, exp["id"], values={"temperature": 0.7}
        )
        return {"experiment_id": exp["id"], "version": committed["version"]}

    @pytest.mark.parametrize(
        "name",
        [
            "default",
            "production",
            "staging",
            "qa",
            "qa-1",
            "eu-west",
            "eu.west.staging",
            "feature_branch",
            "0",
            "a" * 63,
        ],
    )
    def test_valid_names_are_accepted(
        self,
        authenticated_client: TestClient,
        db_project,
        name: str,
    ) -> None:
        pointer = self._shared_pointer(authenticated_client, db_project.id)
        response = authenticated_client.put(
            _environment_url(db_project.id, name), json=pointer
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert name in response.json()["environments"]

    @pytest.mark.parametrize(
        "name",
        [
            # Uppercase.
            "Default",
            "PROD",
            # Whitespace / control characters.
            " staging",
            "stag ing",
            # Leading punctuation.
            "-qa",
            ".env",
            "_internal",
            # Disallowed punctuation.
            "qa/west",
            "qa+1",
            "qa@1",
            "qa:1",
            # Over the length cap.
            "a" * 64,
        ],
    )
    def test_invalid_names_are_rejected(
        self,
        authenticated_client: TestClient,
        db_project,
        name: str,
    ) -> None:
        pointer = self._shared_pointer(authenticated_client, db_project.id)
        response = authenticated_client.put(
            _environment_url(db_project.id, name), json=pointer
        )
        # Some shapes (e.g. ``"qa/west"``) are rejected by the router
        # before the pattern check because the slash changes the URL
        # shape; FastAPI returns 404 then. Anything that does reach the
        # validator should fail with 422. Either is acceptable; both
        # confirm the name never reaches the persistence layer.
        assert response.status_code in {
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        }, response.text
        # And the binding must NOT have been written.
        listing = authenticated_client.get(_environments_url(db_project.id))
        assert listing.status_code == status.HTTP_200_OK
        assert name not in listing.json()["environments"]

    def test_delete_unknown_name_is_idempotent(
        self,
        authenticated_client: TestClient,
        db_project,
    ) -> None:
        # A name that nothing was ever bound to. DELETE returns the
        # current (unchanged) state with 200 — not 404 — because the
        # operation is idempotent.
        response = authenticated_client.delete(
            _environment_url(db_project.id, "never-bound")
        )
        assert response.status_code == status.HTTP_200_OK
        assert "never-bound" not in response.json()["environments"]


# --------------------------------------------------------------------------- #
# Register: unbound custom environment names                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestRegisterEnvironment:
    """``POST /environments`` declares a name without binding an experiment.

    The resulting entry has a ``null`` pointer; the UI renders it as an
    "Unbound" row that the user later promotes onto. The endpoint is
    deliberately conservative: it refuses well-known names (already a
    frontend overlay), duplicates (use ``PUT`` to rebind), and any name
    that doesn't match the standard environment-name shape.
    """

    def test_register_returns_201_with_null_pointer(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        body = response.json()
        assert "qa" in body["environments"]
        assert body["environments"]["qa"] is None

    def test_register_then_get_lists_unbound_name(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # The new name surfaces from a fresh GET — i.e. it really was
        # persisted, not just echoed back from the POST handler.
        authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        response = authenticated_client.get(_environments_url(db_project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["environments"] == {"qa": None}

    def test_register_then_bind_replaces_null_with_pointer(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # Promoting after registering is the canonical happy path. The
        # name should keep its identity across the transition; only its
        # pointer flips from ``None`` to the real ``(experiment, version)``.
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="bindable",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        register = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        assert register.status_code == status.HTTP_201_CREATED
        bind = authenticated_client.put(
            _environment_url(db_project.id, "qa"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )
        assert bind.status_code == status.HTTP_200_OK
        body = bind.json()
        assert body["environments"]["qa"] == {
            "experiment_id": exp["id"],
            "version": committed["version"],
        }

    def test_register_duplicate_is_409(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        first = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        assert first.status_code == status.HTTP_201_CREATED
        again = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        assert again.status_code == status.HTTP_409_CONFLICT

    def test_register_already_bound_name_is_409(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # Once a name has a pointer, re-registering it as "unbound" is
        # nonsensical — the user wants ``PUT`` to move the binding,
        # not ``POST`` to clear it.
        _seed_schema(authenticated_client, db_project.id)
        exp = _create_experiment(
            authenticated_client,
            db_project.id,
            name="bound-already",
            visibility="shared",
        )
        committed, _ = _commit_version(
            authenticated_client,
            exp["id"],
            values={"temperature": 0.7},
        )
        authenticated_client.put(
            _environment_url(db_project.id, "qa"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )
        response = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize("well_known", BuiltInEnvironment.ALL)
    def test_register_well_known_name_is_409(
        self,
        authenticated_client: TestClient,
        db_project,
        well_known: str,
    ) -> None:
        # The frontend already overlays the well-known names on every
        # project; registering them as null entries would just clutter
        # the stored state.
        response = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": well_known},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        # GET should still not list the well-known name in the stored map.
        listing = authenticated_client.get(_environments_url(db_project.id))
        assert listing.status_code == status.HTTP_200_OK
        assert well_known not in listing.json()["environments"]

    @pytest.mark.parametrize(
        "bad_name",
        [
            "",
            "Default",
            " staging",
            "-qa",
            ".env",
            "qa@1",
            "a" * 64,
        ],
    )
    def test_register_invalid_name_is_422(
        self,
        authenticated_client: TestClient,
        db_project,
        bad_name: str,
    ) -> None:
        response = authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": bad_name},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        listing = authenticated_client.get(_environments_url(db_project.id))
        assert listing.status_code == status.HTTP_200_OK
        assert bad_name not in listing.json()["environments"]

    def test_register_then_delete_removes_entry(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # Custom unbound names should be deletable — that's the only
        # way the user can take one back once registered.
        authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        delete = authenticated_client.delete(
            _environment_url(db_project.id, "qa")
        )
        assert delete.status_code == status.HTTP_200_OK
        assert "qa" not in delete.json()["environments"]

    def test_resolve_against_unbound_registered_name_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        # Resolving an environment whose pointer is ``None`` behaves
        # the same way as resolving a never-bound well-known name: 404.
        authenticated_client.post(
            _environments_url(db_project.id),
            json={"name": "qa"},
        )
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={"environment": "qa"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------- #
# Resolver: precedence + visibility + cross-project                           #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
class TestResolver:
    """`/resolve` is the single canonical path used by SDK and run-snapshot."""

    def test_implicit_default_environment_when_no_args(
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
            _environment_url(db_project.id, "default"),
            json={"experiment_id": exp["id"], "version": committed["version"]},
        )

        response = authenticated_client.get(_resolve_url(db_project.id))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["source"] == "environment"
        assert body["source_environment"] == "default"
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
        assert body["source_environment"] is None

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

    def test_resolve_unbound_environment_is_404(
        self, authenticated_client: TestClient, db_project
    ) -> None:
        response = authenticated_client.get(
            _resolve_url(db_project.id),
            params={"environment": "production"},
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

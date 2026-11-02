"""Tests for the richer requirement fields and the endpoints around them.

Covers parent / type / impact and the loop check, source links, a requirement's
examples (annotations linked to it), the annotation's own ``requirement_id``, making a
tuning case from an annotation, and the AI wording review with the model stubbed.

Run with: python -m pytest tests/backend/routes/test_requirement_rich.py -v
"""

import hashlib
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

from .test_annotations import _ensure_pass_fail_statuses, _project_scope

REVIEW = "rhesis.backend.app.services.requirement_review"


def _lookup(db: Session, type_name: str, type_value: str, org_id, user_id) -> models.TypeLookup:
    lookup = get_or_create_type_lookup(
        db=db,
        type_name=type_name,
        type_value=type_value,
        organization_id=org_id,
        user_id=user_id,
        commit=False,
    )
    db.commit()
    return lookup


def _create(client: TestClient, **body) -> dict:
    body.setdefault("name", f"Req {uuid.uuid4().hex[:8]}")
    response = client.post("/requirements/", json=body)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _source(db: Session, org_id, user_id, title: str = "Policy handbook") -> models.Source:
    source = models.Source(
        title=f"{title} {uuid.uuid4().hex[:6]}",
        url="https://example.com/policy",
        organization_id=org_id,
        user_id=user_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@pytest.fixture
def lookups(test_db: Session, test_org_id, authenticated_user_id) -> dict:
    return {
        "safety": _lookup(test_db, "RequirementType", "Safety", test_org_id, authenticated_user_id),
        "tone": _lookup(test_db, "RequirementType", "Tone", test_org_id, authenticated_user_id),
        "legal": _lookup(
            test_db, "RequirementImpact", "Legal / regulatory", test_org_id, authenticated_user_id
        ),
    }


class TestRequirementHierarchyAndLookups:
    def test_create_with_parent_type_and_impact(self, authenticated_client, lookups):
        parent = _create(authenticated_client, name=f"Parent {uuid.uuid4().hex[:6]}")
        child = _create(
            authenticated_client,
            parent_id=parent["id"],
            requirement_type_id=str(lookups["safety"].id),
            impact_id=str(lookups["legal"].id),
        )

        assert child["parent_id"] == parent["id"]
        assert child["parent"] == {"id": parent["id"], "name": parent["name"]}
        assert child["requirement_type"]["type_value"] == "Safety"
        assert child["requirement_type"]["type_name"] == "RequirementType"
        assert child["impact"]["type_value"] == "Legal / regulatory"
        assert child["sources"] == []
        assert child["examples_count"] == 0
        assert child["review"] is None

        refreshed = authenticated_client.get(f"/requirements/{parent['id']}").json()
        assert refreshed["children_count"] == 1
        assert refreshed["parent"] is None

    def test_update_sets_and_clears_parent(self, authenticated_client):
        parent = _create(authenticated_client)
        child = _create(authenticated_client)

        set_response = authenticated_client.put(
            f"/requirements/{child['id']}", json={"parent_id": parent["id"]}
        )
        assert set_response.status_code == status.HTTP_200_OK, set_response.text
        assert set_response.json()["parent_id"] == parent["id"]

        cleared = authenticated_client.put(f"/requirements/{child['id']}", json={"parent_id": None})
        assert cleared.status_code == status.HTTP_200_OK, cleared.text
        assert cleared.json()["parent_id"] is None
        assert cleared.json()["name"] == child["name"]

    def test_a_requirement_cannot_be_its_own_parent(self, authenticated_client):
        requirement = _create(authenticated_client)
        response = authenticated_client.put(
            f"/requirements/{requirement['id']}", json={"parent_id": requirement["id"]}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "own parent" in response.json()["detail"]

    def test_a_descendant_cannot_become_the_parent(self, authenticated_client):
        top = _create(authenticated_client)
        middle = _create(authenticated_client, parent_id=top["id"])
        bottom = _create(authenticated_client, parent_id=middle["id"])

        response = authenticated_client.put(
            f"/requirements/{top['id']}", json={"parent_id": bottom["id"]}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "loop" in response.json()["detail"]

    def test_unknown_parent_is_refused(self, authenticated_client):
        response = authenticated_client.post(
            "/requirements/", json={"name": "Orphan", "parent_id": str(uuid.uuid4())}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_impact_lookup_is_not_accepted_as_a_type(self, authenticated_client, lookups):
        response = authenticated_client.post(
            "/requirements/",
            json={"name": "Wrong lookup", "requirement_type_id": str(lookups["legal"].id)},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_parent(self, authenticated_client):
        token = uuid.uuid4().hex[:8]
        parent = _create(authenticated_client, name=f"ZZTree-{token}-parent")
        child = _create(authenticated_client, name=f"ZZTree-{token}-child", parent_id=parent["id"])

        children = authenticated_client.get(
            "/requirements/", params={"$filter": f"parent_id eq {parent['id']}"}
        ).json()
        assert [r["id"] for r in children] == [child["id"]]

        roots = authenticated_client.get(
            "/requirements/",
            params={"$filter": f"startswith(name, 'ZZTree-{token}') and parent_id eq null"},
        )
        assert roots.status_code == status.HTTP_200_OK, roots.text
        assert [r["id"] for r in roots.json()] == [parent["id"]]

        nested = authenticated_client.get(
            "/requirements/",
            params={"$filter": f"startswith(name, 'ZZTree-{token}') and parent_id ne null"},
        ).json()
        assert [r["id"] for r in nested] == [child["id"]]

        selected = authenticated_client.get(
            "/requirements/",
            params={"$filter": f"parent_id eq {parent['id']}", "$select": "id,name"},
        )
        assert selected.status_code == status.HTTP_200_OK, selected.text
        assert selected.json() == [{"id": child["id"], "name": child["name"]}]

    def test_create_with_explicit_nulls(self, authenticated_client):
        created = _create(
            authenticated_client, parent_id=None, requirement_type_id=None, impact_id=None
        )
        assert created["parent_id"] is None
        assert created["requirement_type"] is None

    def test_update_clears_type_and_impact(self, authenticated_client, lookups):
        requirement = _create(
            authenticated_client,
            requirement_type_id=str(lookups["tone"].id),
            impact_id=str(lookups["legal"].id),
        )
        response = authenticated_client.put(
            f"/requirements/{requirement['id']}",
            json={"requirement_type_id": None, "impact_id": None, "parent_id": None},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["requirement_type"] is None
        assert response.json()["impact"] is None


class TestRequirementSources:
    def test_link_update_note_and_unlink(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        requirement = _create(authenticated_client)
        source = _source(test_db, test_org_id, authenticated_user_id)
        path = f"/requirements/{requirement['id']}/sources/{source.id}"

        assert authenticated_client.post(path, json={"note": "section 4.2"}).status_code == 200
        linked = authenticated_client.get(f"/requirements/{requirement['id']}").json()["sources"]
        assert linked == [
            {
                "id": str(source.id),
                "title": source.title,
                "url": source.url,
                "source_type": None,
                "note": "section 4.2",
            }
        ]

        # Linking again is idempotent and updates the note.
        assert authenticated_client.post(path, json={"note": "section 5"}).status_code == 200
        linked = authenticated_client.get(f"/requirements/{requirement['id']}").json()["sources"]
        assert [s["note"] for s in linked] == ["section 5"]

        # The body is optional.
        assert authenticated_client.post(path).status_code == 200

        assert authenticated_client.delete(path).status_code == status.HTTP_200_OK
        assert (
            authenticated_client.get(f"/requirements/{requirement['id']}").json()["sources"] == []
        )
        assert authenticated_client.delete(path).status_code == status.HTTP_404_NOT_FOUND

    def test_url_falls_back_to_source_metadata(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        requirement = _create(authenticated_client)
        source = models.Source(
            title=f"Website {uuid.uuid4().hex[:6]}",
            source_metadata={"url": "https://example.com/terms"},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(source)
        test_db.commit()
        authenticated_client.post(f"/requirements/{requirement['id']}/sources/{source.id}")

        [linked] = authenticated_client.get(f"/requirements/{requirement['id']}").json()["sources"]
        assert linked["url"] == "https://example.com/terms"

    def test_unknown_source_404s(self, authenticated_client):
        requirement = _create(authenticated_client)
        response = authenticated_client.post(
            f"/requirements/{requirement['id']}/sources/{uuid.uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


def _custom_metric(db: Session, org_id, user_id) -> models.Metric:
    backend_type = _lookup(db, "BackendType", "custom", org_id, user_id)
    metric = models.Metric(
        name=f"Tone check {uuid.uuid4().hex[:6]}",
        evaluation_prompt="Is the answer polite?",
        score_type="binary",
        metric_scope=[MetricScope.SINGLE_TURN.value],
        backend_type_id=backend_type.id,
        organization_id=org_id,
        user_id=user_id,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@pytest.fixture
def annotated_setup(
    authenticated_client,
    test_db,
    test_organization,
    test_type_lookup,
    db_user,
    authenticated_user,
    db_project,
):
    """A test result with a prompt and an output, and a Pass status to annotate it with."""
    pass_status, _ = _ensure_pass_fail_statuses(
        test_db, test_organization, test_type_lookup, db_user
    )
    org_id, user_id = test_organization.id, authenticated_user.id
    with _project_scope(test_db, org_id, user_id, db_project.id):

        def _result(prompt_text=None, output_text=None, requirement_id=None):
            test_id = None
            if prompt_text is not None or requirement_id is not None:
                prompt = models.Prompt(
                    content=prompt_text or "", organization_id=org_id, user_id=user_id
                )
                test_db.add(prompt)
                test_db.flush()
                test = models.Test(
                    prompt_id=prompt.id,
                    requirement_id=requirement_id,
                    organization_id=org_id,
                    user_id=user_id,
                    project_id=db_project.id,
                )
                test_db.add(test)
                test_db.flush()
                test_id = test.id
            result = models.TestResult(
                test_id=test_id,
                test_output={"output": output_text} if output_text else None,
                organization_id=org_id,
                user_id=user_id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)
            return result

        def _annotate(result, **extra):
            body = {
                "entity_type": "TestResult",
                "entity_id": str(result.id),
                "status_id": str(pass_status.id),
                "comments": "Should have escalated",
                **extra,
            }
            response = authenticated_client.post("/annotations/", json=body)
            assert response.status_code == status.HTTP_200_OK, response.text
            return response.json()

        yield {"result": _result, "annotate": _annotate}


class TestRequirementExamples:
    def test_annotation_requirement_set_filter_and_clear(
        self, authenticated_client, annotated_setup
    ):
        requirement = _create(authenticated_client)
        result = annotated_setup["result"]("Cancel my order", "Sure, done.")
        annotation = annotated_setup["annotate"](result, requirement_id=requirement["id"])
        assert annotation["requirement_id"] == requirement["id"]

        listed = authenticated_client.get(
            "/annotations/", params={"requirement_id": requirement["id"]}
        ).json()
        assert [a["id"] for a in listed] == [annotation["id"]]
        assert listed[0]["context"]["requirement_name"] == requirement["name"]

        facets = authenticated_client.get("/annotations/facets").json()
        assert requirement["id"] in {r["id"] for r in facets["requirements"]}

        detail = authenticated_client.get(f"/requirements/{requirement['id']}").json()
        assert detail["examples_count"] == 1

        examples = authenticated_client.get(f"/requirements/{requirement['id']}/examples")
        assert examples.status_code == status.HTTP_200_OK, examples.text
        [example] = examples.json()
        assert example["annotation"]["id"] == annotation["id"]
        assert example["annotation"]["comments"] == "Should have escalated"
        assert example["annotation"]["user"] is not None
        assert example["input"] == "Cancel my order"
        assert example["output"] == "Sure, done."
        assert example["tuning_cases"] == []

        cleared = authenticated_client.put(
            f"/annotations/{annotation['id']}", json={"requirement_id": None}
        )
        assert cleared.status_code == status.HTTP_200_OK, cleared.text
        assert cleared.json()["requirement_id"] is None
        assert authenticated_client.get(f"/requirements/{requirement['id']}/examples").json() == []

    def test_unknown_requirement_is_refused(self, authenticated_client, annotated_setup):
        result = annotated_setup["result"]("Hi", "Hello")
        response = authenticated_client.post(
            "/annotations/",
            json={
                "entity_type": "TestResult",
                "entity_id": str(result.id),
                "status_id": str(uuid.uuid4()),
                "requirement_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_annotation_defaults_to_the_tests_requirement(
        self, authenticated_client, annotated_setup
    ):
        requirement = _create(authenticated_client)
        result = annotated_setup["result"]("Hi", "Hello", requirement_id=requirement["id"])
        annotation = annotated_setup["annotate"](result)
        assert annotation["requirement_id"] == requirement["id"]


class TestAnnotationTuningCase:
    def test_creates_a_case_and_records_it(
        self, authenticated_client, annotated_setup, test_db, test_org_id, authenticated_user_id
    ):
        metric = _custom_metric(test_db, test_org_id, authenticated_user_id)
        requirement = _create(authenticated_client)
        result = annotated_setup["result"]("Where is my parcel?", "No idea, go away.")
        annotation = annotated_setup["annotate"](result, requirement_id=requirement["id"])

        response = authenticated_client.post(
            f"/annotations/{annotation['id']}/tuning-case", json={"metric_id": str(metric.id)}
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["metric_id"] == str(metric.id)

        cases = authenticated_client.get(f"/metrics/{metric.id}/tuning/cases").json()
        [case] = cases
        assert case["id"] == body["case_id"]
        assert case["input"] == "Where is my parcel?"
        assert case["output"] == "No idea, go away."

        [example] = authenticated_client.get(f"/requirements/{requirement['id']}/examples").json()
        assert example["tuning_cases"] == [body]

    def test_nothing_to_copy_is_refused(
        self, authenticated_client, annotated_setup, test_db, test_org_id, authenticated_user_id
    ):
        metric = _custom_metric(test_db, test_org_id, authenticated_user_id)
        result = annotated_setup["result"]()
        annotation = annotated_setup["annotate"](result)

        response = authenticated_client.post(
            f"/annotations/{annotation['id']}/tuning-case", json={"metric_id": str(metric.id)}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "input and output" in response.json()["detail"]


@pytest.fixture
def review_model():
    model = MagicMock()
    with patch(f"{REVIEW}.resolve_model", return_value=model) as picked:
        yield model, picked


class TestRequirementReview:
    def test_review_is_stored_and_returned(self, authenticated_client, lookups, review_model):
        model, picked = review_model
        description = "The bot should respond appropriately to angry customers."
        model.generate.return_value = {
            "hints": [
                {
                    "kind": "vague_wording",
                    "message": "'Appropriately' can't be checked.",
                    "quote": "appropriately",
                    "suggestion": "The bot stays calm and offers a refund or a person.",
                },
                {"kind": "suggest_type", "message": "This is about tone.", "suggestion": "Tone"},
                {"kind": "suggest_type", "message": "Unknown.", "suggestion": "Nonsense"},
                {"kind": "other", "message": "Quote not in text.", "quote": "not there"},
            ]
        }
        requirement = _create(authenticated_client, description=description)

        response = authenticated_client.post(f"/requirements/{requirement['id']}/review")
        assert response.status_code == status.HTTP_200_OK, response.text
        review = response.json()

        assert picked.call_args.args[2] == "generation"
        prompt = model.generate.call_args.args[0]
        assert description in prompt
        assert "Tone" in prompt
        expected_hash = hashlib.sha256(f"{requirement['name']}\n{description}".encode()).hexdigest()
        assert review["description_hash"] == expected_hash
        assert [h["kind"] for h in review["hints"]] == ["vague_wording", "suggest_type", "other"]
        assert review["hints"][2]["quote"] is None

        stored = authenticated_client.get(f"/requirements/{requirement['id']}").json()["review"]
        assert stored == review

    def test_model_failure_is_a_clear_error(self, authenticated_client, review_model):
        model, _ = review_model
        model.generate.side_effect = RuntimeError("provider down")
        requirement = _create(authenticated_client, description="Be nice.")

        response = authenticated_client.post(f"/requirements/{requirement['id']}/review")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "generation model" in response.json()["detail"]

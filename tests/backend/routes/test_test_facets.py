"""
Tests for GET /tests/facets endpoint.

The endpoint backs the test filter drawers: it returns the distinct
requirement/category/topic/test-type values that actually appear on visible
tests, so a drawer only offers values its grid can match.

Names are suffixed with a per-run token so assertions stay valid regardless of
what other fixtures leave in the organization.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.test import test_test_set_association


@pytest.fixture
def facet_scenario(test_db: Session, test_organization, db_user, db_status, db_test_set) -> dict:
    """Build tests whose lookup values cover every visibility case the query handles.

    Returns the unique names so each test can assert on its own rows only.
    """
    token = uuid.uuid4().hex[:8]
    org_id, user_id = test_organization.id, db_user.id

    def _lookup(model, name):
        row = model(name=name, organization_id=org_id, user_id=user_id)
        test_db.add(row)
        return row

    names = {
        "linked_req": f"ZZFacetReqLinked-{token}",
        "unlinked_req": f"ZZFacetReqUnlinked-{token}",
        "deleted_req": f"ZZFacetReqDeleted-{token}",
        "explorer_req": f"ZZFacetReqExplorer-{token}",
        "category": f"ZZFacetCategory-{token}",
        "topic": f"ZZFacetTopic-{token}",
        "test_type": f"ZZFacetType-{token}",
    }

    linked_req = _lookup(models.Requirement, names["linked_req"])
    unlinked_req = _lookup(models.Requirement, names["unlinked_req"])
    deleted_req = _lookup(models.Requirement, names["deleted_req"])
    explorer_req = _lookup(models.Requirement, names["explorer_req"])
    category = _lookup(models.Category, names["category"])
    topic = _lookup(models.Topic, names["topic"])

    test_type = models.TypeLookup(
        type_name="TestType",
        type_value=names["test_type"],
        organization_id=org_id,
        user_id=user_id,
    )
    test_db.add(test_type)
    test_db.flush()

    def _test(**kwargs):
        row = models.Test(
            organization_id=org_id,
            user_id=user_id,
            status_id=db_status.id,
            **kwargs,
        )
        test_db.add(row)
        return row

    # Visible, and linked to the test set: the only row a scoped query may see.
    linked = _test(
        requirement_id=linked_req.id,
        category_id=category.id,
        topic_id=topic.id,
        test_type_id=test_type.id,
    )
    # Visible, but outside the test set.
    _test(requirement_id=unlinked_req.id)
    # Excluded rows: each one previously leaked its value into the drawer.
    _test(requirement_id=deleted_req.id, deleted_at=datetime.now(timezone.utc))
    _test(requirement_id=explorer_req.id, explorer_row=True)
    test_db.flush()

    test_db.execute(
        test_test_set_association.insert().values(
            test_id=linked.id,
            test_set_id=db_test_set.id,
            organization_id=org_id,
            user_id=user_id,
        )
    )
    test_db.flush()

    return {"names": names, "test_set_id": db_test_set.id}


class TestGetTestFacets:
    """Tests for GET /tests/facets"""

    def test_returns_values_from_visible_tests(
        self, authenticated_client: TestClient, facet_scenario
    ):
        """Every facet reports the value carried by a visible test."""
        names = facet_scenario["names"]

        response = authenticated_client.get("/tests/facets")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert names["linked_req"] in data["requirements"]
        assert names["unlinked_req"] in data["requirements"]
        assert names["category"] in data["categories"]
        assert names["topic"] in data["topics"]
        assert names["test_type"] in data["test_types"]

    def test_excludes_soft_deleted_tests(self, authenticated_client: TestClient, facet_scenario):
        """A soft-deleted test contributes nothing.

        Regression test: the ambient soft-delete listener does not reach the
        joined Test in this column-narrowed query, so the predicate is explicit
        in the CRUD layer. Without it the drawer offered dead values.
        """
        names = facet_scenario["names"]

        response = authenticated_client.get("/tests/facets")

        assert response.status_code == status.HTTP_200_OK
        assert names["deleted_req"] not in response.json()["requirements"]

    def test_excludes_explorer_rows(self, authenticated_client: TestClient, facet_scenario):
        """Explorer-owned tests are absent, matching what GET /tests lists."""
        names = facet_scenario["names"]

        response = authenticated_client.get("/tests/facets")

        assert response.status_code == status.HTTP_200_OK
        assert names["explorer_req"] not in response.json()["requirements"]

    def test_scopes_to_test_set(self, authenticated_client: TestClient, facet_scenario):
        """test_set_id narrows facets to values on tests linked to that set."""
        names = facet_scenario["names"]

        response = authenticated_client.get(
            "/tests/facets", params={"test_set_id": str(facet_scenario["test_set_id"])}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["requirements"] == [names["linked_req"]]
        assert data["categories"] == [names["category"]]
        assert data["topics"] == [names["topic"]]
        assert data["test_types"] == [names["test_type"]]

    def test_unknown_test_set_returns_empty_facets(
        self, authenticated_client: TestClient, facet_scenario
    ):
        """An unknown test set yields empty lists rather than unscoped values."""
        response = authenticated_client.get(
            "/tests/facets", params={"test_set_id": str(uuid.uuid4())}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "requirements": [],
            "categories": [],
            "topics": [],
            "test_types": [],
        }

    def test_rejects_malformed_test_set_id(self, authenticated_client: TestClient):
        """A non-UUID test_set_id is a validation error, not a silent full scan."""
        response = authenticated_client.get("/tests/facets", params={"test_set_id": "not-a-uuid"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_requires_authentication(self, client: TestClient):
        """Unauthenticated requests are rejected."""
        response = client.get("/tests/facets")

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

"""Foreign ids in a request body are checked against the caller's organization.

Org A is the authenticated test org. Org B is created per test. Every write below goes
through the real route, and no response may carry anything from org B.
"""

import uuid

import pytest
from fastapi import status

from rhesis.backend.app import models
from tests.backend.fixtures.rls import as_project, scope_to_org
from tests.backend.fixtures.test_setup import (
    create_test_api_token,
    create_test_organization_and_user,
    create_test_user,
)


@pytest.fixture
def org_b(test_db, test_org_id):
    """Another org with its own user and project; the session is scoped back to org A."""
    suffix = uuid.uuid4().hex[:8]
    org, user, _ = create_test_organization_and_user(
        test_db, f"Foreign Org {suffix}", f"foreign-{suffix}@security-test.com", "Foreign User"
    )
    project = models.Project(name=f"B project {suffix}", organization_id=org.id, user_id=user.id)
    test_db.add(project)
    test_db.flush()
    ids = {
        "org_id": str(org.id),
        "user_id": str(user.id),
        "email": user.email,
        "project_id": str(project.id),
    }
    scope_to_org(test_db, test_org_id)
    return ids


def _assert_no_org_b(response, org_b):
    body = response.text
    for key in ("org_id", "user_id", "email", "project_id"):
        assert org_b[key] not in body, f"org B {key} leaked: {body}"


def _create_row(test_db, model, org_id, user_id, **fields):
    row = model(organization_id=org_id, user_id=user_id, **fields)
    test_db.add(row)
    test_db.flush()
    return row


@pytest.mark.security
class TestUserReferenceFields:
    def test_create_source_with_foreign_user_id_is_rejected(self, authenticated_client, org_b):
        response = authenticated_client.post(
            "/sources/", json={"title": "x", "user_id": org_b["user_id"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    @pytest.mark.parametrize("field", ["owner_id", "user_id"])
    def test_create_project_with_foreign_user_is_rejected(self, authenticated_client, org_b, field):
        response = authenticated_client.post(
            "/projects/", json={"name": "x", field: org_b["user_id"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    @pytest.mark.parametrize("field", ["owner_id", "assignee_id"])
    def test_update_test_with_foreign_user_is_rejected(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, org_b, field
    ):
        test = _create_row(test_db, models.Test, test_org_id, authenticated_user_id)

        response = authenticated_client.put(f"/tests/{test.id}", json={field: org_b["user_id"]})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)
        test_db.refresh(test)
        assert getattr(test, field) is None

    @pytest.mark.parametrize("field", ["owner_id", "assignee_id"])
    def test_update_test_set_with_foreign_user_is_rejected(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, org_b, field
    ):
        test_set = _create_row(
            test_db, models.TestSet, test_org_id, authenticated_user_id, name="A set"
        )

        response = authenticated_client.put(
            f"/test_sets/{test_set.id}", json={field: org_b["user_id"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    def test_update_project_with_foreign_owner_is_rejected(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, org_b
    ):
        project = _create_row(
            test_db, models.Project, test_org_id, authenticated_user_id, name="A project"
        )

        response = authenticated_client.put(
            f"/projects/{project.id}", json={"owner_id": org_b["user_id"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    def test_bulk_create_tests_with_foreign_assignee_is_rejected(self, authenticated_client, org_b):
        test = {
            "prompt": {"content": "hello", "language_code": "en"},
            "requirement": "r",
            "category": "c",
            "topic": "t",
            "assignee_id": org_b["user_id"],
        }

        response = authenticated_client.post("/tests/bulk", json={"tests": [test]})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    def test_same_org_user_is_accepted(self, authenticated_client, authenticated_user_id):
        response = authenticated_client.post(
            "/projects/", json={"name": "x", "owner_id": authenticated_user_id}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["owner_id"] == authenticated_user_id


@pytest.mark.security
class TestOrganizationAndProjectIds:
    def test_body_organization_id_is_replaced_by_callers(
        self, authenticated_client, test_db, test_org_id, org_b
    ):
        response = authenticated_client.post(
            "/sources/", json={"title": "x", "organization_id": org_b["org_id"]}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["organization_id"] == test_org_id
        _assert_no_org_b(response, org_b)
        row = test_db.get(models.Source, uuid.UUID(response.json()["id"]))
        assert str(row.organization_id) == test_org_id

    def test_foreign_project_id_is_rejected(self, authenticated_client, org_b):
        response = authenticated_client.post(
            "/sources/", json={"title": "x", "project_id": org_b["project_id"]}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_no_org_b(response, org_b)

    def test_same_org_project_requires_membership(
        self, client, test_db, test_org_id, authenticated_user_id
    ):
        suffix = uuid.uuid4().hex[:8]
        member = create_test_user(test_db, test_org_id, f"member-{suffix}@security-test.com")
        token = create_test_api_token(test_db, member)
        other = _create_row(
            test_db, models.Project, test_org_id, authenticated_user_id, name="not mine"
        )
        mine = _create_row(test_db, models.Project, test_org_id, member.id, name="mine")
        test_db.add(
            models.ProjectMembership(
                project_id=mine.id, user_id=member.id, organization_id=test_org_id
            )
        )
        test_db.flush()
        headers = {"Authorization": f"Bearer {token.token}"}

        denied = client.post(
            "/sources/", json={"title": "x", "project_id": str(other.id)}, headers=headers
        )
        # RLS also needs the project GUC to accept the row; the app check does not.
        with as_project(test_db, mine.id):
            allowed = client.post(
                "/sources/", json={"title": "x", "project_id": str(mine.id)}, headers=headers
            )

        assert denied.status_code == status.HTTP_400_BAD_REQUEST
        assert allowed.status_code == status.HTTP_200_OK, allowed.text
        assert allowed.json()["project_id"] == str(mine.id)


@pytest.mark.security
class TestNestedUserSerialization:
    def test_stored_foreign_user_is_not_serialized(
        self, authenticated_client, test_db, test_org_id, org_b
    ):
        # A row written before the write-time check existed.
        source = _create_row(test_db, models.Source, test_org_id, org_b["user_id"], title="old")

        response = authenticated_client.get(f"/sources/{source.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user"] is None
        assert org_b["email"] not in response.text

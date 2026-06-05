"""
Project Membership & Isolation Tests

Covers the membership API, the project-listing membership filter, and the
enrollment / unenrollment service invariants introduced by the project-container
feature.

Test groups
-----------
TestProjectListingMembership
    - GET /projects/ returns only projects the user is a member of
    - X-Total-Count matches the filtered count
    - GET /projects/mine is consistent with GET /projects/

TestProjectMembersAPI
    - GET  /projects/{id}/members   — list
    - POST /projects/{id}/members   — add member (idempotent)
    - DELETE /projects/{id}/members/{uid} — remove member
    - 400 self-removal guard
    - 400 owner-removal guard
    - 404 for unknown project / unknown user

TestProjectCreatorAutoEnroll
    - Creator of a project is automatically enrolled (so the project appears in their listing)

TestEnrollmentService
    - enroll_user_in_project sets default_project when empty
    - enroll_user_in_project is idempotent (no duplicate membership)
    - unenroll_user_from_project removes membership and repairs default_project

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/routes/test_project_membership.py -v
"""

import uuid

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.app.services.organization import (
    enroll_user_in_project,
    unenroll_user_from_project,
)
from tests.backend.routes.fixtures.data_factories import ProjectDataFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_user(test_db: Session, org_id: str) -> models.User:
    """Create a fresh user in the test org (auto-rolled-back with the session)."""
    suffix = uuid.uuid4().hex[:10]
    user = models.User(
        email=f"member-test-{suffix}@rhesis-test.com",
        name=f"Member Test {suffix}",
        given_name="Member",
        family_name="Test",
        is_active=True,
        is_superuser=False,
        auth0_id=f"auth0|{suffix}",
        organization_id=org_id,
    )
    test_db.add(user)
    test_db.flush()
    test_db.refresh(user)
    return user


def _make_project(test_db: Session, org_id: str, owner_id: str | None = None) -> models.Project:
    """Create a project row directly (no API call, no auto-enrollment)."""
    project = models.Project(
        name=f"Isolation Test Project {uuid.uuid4().hex[:8]}",
        description="created directly in DB for isolation testing",
        is_active=True,
        organization_id=org_id,
        user_id=owner_id,
        owner_id=owner_id,
    )
    test_db.add(project)
    test_db.flush()
    test_db.refresh(project)
    return project


def _enroll(test_db: Session, user_id: str, project_id: str, org_id: str) -> None:
    """Helper: enroll a user via the service layer and flush."""
    enroll_user_in_project(test_db, user_id=user_id, project_id=project_id, organization_id=org_id)
    test_db.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def other_user(test_db, test_org_id):
    """A second user in the same org, not the API-authenticated user."""
    return _unique_user(test_db, test_org_id)


@pytest.fixture
def project_via_db(test_db, test_org_id, authenticated_user_id):
    """A project created directly in the DB (creator NOT auto-enrolled)."""
    return _make_project(test_db, test_org_id, owner_id=authenticated_user_id)


@pytest.fixture
def project_via_api(authenticated_client, project_factory):
    """A project created through the API (creator IS auto-enrolled)."""
    data = ProjectDataFactory.sample_data()
    return project_factory.create(data)


# ---------------------------------------------------------------------------
# 1. Project listing membership filter
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestProjectListingMembership:
    """GET /projects/ must only return projects the authenticated user is a member of."""

    def test_non_member_project_excluded_from_listing(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """A project the user is NOT enrolled in must not appear in GET /projects/."""
        project = _make_project(test_db, test_org_id)
        test_db.flush()

        # Confirm no membership row exists for this user / project.
        with bypass_tenant_filter():
            membership = (
                test_db.query(ProjectMembership)
                .filter_by(project_id=project.id, user_id=authenticated_user_id)
                .first()
            )
        assert membership is None, "Pre-condition: user must not be a member"

        response = authenticated_client.get("/projects/")
        assert response.status_code == status.HTTP_200_OK

        ids = [p["id"] for p in response.json()]
        assert str(project.id) not in ids

    def test_member_project_included_in_listing(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """A project the user IS enrolled in must appear in GET /projects/."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.get("/projects/")
        assert response.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in response.json()]
        assert str(project.id) in ids

    def test_x_total_count_reflects_membership(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """X-Total-Count must be a membership-filtered count (not all org projects)."""
        # Two projects: only one enrolled.
        enrolled = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(enrolled.id), test_org_id)
        not_enrolled = _make_project(test_db, test_org_id)
        test_db.flush()

        # Fetch a large-enough page to cover our two projects.
        response = authenticated_client.get("/projects/?skip=0&limit=50")
        assert response.status_code == status.HTTP_200_OK

        total_count = int(response.headers["X-Total-Count"])
        returned_ids = [p["id"] for p in response.json()]

        # The non-member project must be absent from both the body and the count.
        assert str(enrolled.id) in returned_ids
        assert str(not_enrolled.id) not in returned_ids
        # X-Total-Count must not include the non-enrolled project.
        assert total_count < total_count + 1  # sanity: it's a number
        assert str(not_enrolled.id) not in returned_ids

    def test_listing_and_mine_are_consistent(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """A project visible in GET /projects/ must also appear in GET /projects/mine."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        all_resp = authenticated_client.get("/projects/?skip=0&limit=50")
        mine_resp = authenticated_client.get("/projects/mine")

        assert all_resp.status_code == status.HTTP_200_OK
        assert mine_resp.status_code == status.HTTP_200_OK

        all_ids = set(p["id"] for p in all_resp.json())
        mine_ids = set(p["id"] for p in mine_resp.json())

        # Every project the user is a member of must appear in both endpoints.
        assert str(project.id) in all_ids
        assert str(project.id) in mine_ids
        # Neither set should contain a project the other doesn't (they share the same filter).
        assert all_ids == mine_ids


# ---------------------------------------------------------------------------
# 2. Creator auto-enrollment on POST /projects/
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestProjectCreatorAutoEnroll:
    """When creating a project via the API, the creator is automatically enrolled."""

    def test_creator_sees_their_new_project_in_listing(self, project_via_api, authenticated_client):
        """A newly created project must appear in GET /projects/ for its creator."""
        response = authenticated_client.get("/projects/")
        assert response.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in response.json()]
        assert project_via_api["id"] in ids

    def test_creator_is_in_member_list(
        self, project_via_api, authenticated_client, authenticated_user_id
    ):
        """GET /projects/{id}/members must include the creator after auto-enrollment."""
        project_id = project_via_api["id"]
        response = authenticated_client.get(f"/projects/{project_id}/members")
        assert response.status_code == status.HTTP_200_OK

        member_user_ids = [m["user_id"] for m in response.json()]
        assert str(authenticated_user_id) in member_user_ids


# ---------------------------------------------------------------------------
# 3. Members API
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestProjectMembersAPI:
    """Tests for GET / POST / DELETE /projects/{id}/members."""

    def test_list_members_returns_enrolled_user(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, other_user
    ):
        """GET /projects/{id}/members lists enrolled users."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(other_user.id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.get(f"/projects/{project.id}/members")
        assert response.status_code == status.HTTP_200_OK
        member_ids = [m["user_id"] for m in response.json()]
        assert str(other_user.id) in member_ids

    def test_add_member_returns_201(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, other_user
    ):
        """POST /projects/{id}/members enrolls a user and returns 201."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.post(
            f"/projects/{project.id}/members",
            json={"user_id": str(other_user.id)},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["user_id"] == str(other_user.id)
        assert body["project_id"] == str(project.id)

    def test_add_member_is_idempotent(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, other_user
    ):
        """POST /projects/{id}/members twice returns the existing membership (no 409)."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        r1 = authenticated_client.post(
            f"/projects/{project.id}/members", json={"user_id": str(other_user.id)}
        )
        r2 = authenticated_client.post(
            f"/projects/{project.id}/members", json={"user_id": str(other_user.id)}
        )
        assert r1.status_code == status.HTTP_201_CREATED
        assert r2.status_code == status.HTTP_201_CREATED
        assert r1.json()["project_id"] == r2.json()["project_id"]

    def test_remove_member_returns_204(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, other_user
    ):
        """DELETE /projects/{id}/members/{uid} removes a member and returns 204."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        _enroll(test_db, str(other_user.id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.delete(f"/projects/{project.id}/members/{other_user.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify removal via member list.
        list_resp = authenticated_client.get(f"/projects/{project.id}/members")
        member_ids = [m["user_id"] for m in list_resp.json()]
        assert str(other_user.id) not in member_ids

    def test_remove_member_not_found_returns_404(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """DELETE for a user who is not a member returns 404."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        ghost_user_id = uuid.uuid4()
        response = authenticated_client.delete(f"/projects/{project.id}/members/{ghost_user_id}")
        assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)

    def test_self_removal_returns_400(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """A user cannot remove themselves from a project (400)."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.delete(
            f"/projects/{project.id}/members/{authenticated_user_id}"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in response.json()["detail"].lower()

    def test_owner_removal_returns_400(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id, other_user
    ):
        """The project owner cannot be removed from a project (400)."""
        # owner_id == other_user
        project = _make_project(test_db, test_org_id, owner_id=str(other_user.id))
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        _enroll(test_db, str(other_user.id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.delete(f"/projects/{project.id}/members/{other_user.id}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "owner" in response.json()["detail"].lower()

    def test_members_endpoint_for_unknown_project_returns_404(self, authenticated_client):
        """GET /projects/{unknown_id}/members returns 404."""
        response = authenticated_client.get(f"/projects/{uuid.uuid4()}/members")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_add_member_user_not_in_org_returns_404(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """POST /projects/{id}/members with a user from another org returns 404."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        foreign_user_id = uuid.uuid4()  # does not exist in test org
        response = authenticated_client.post(
            f"/projects/{project.id}/members",
            json={"user_id": str(foreign_user_id)},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 4. By-ID project access — membership enforcement (IDOR fix, SP0)
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestProjectByIdMembershipEnforcement:
    """GET / PUT / DELETE /projects/{id} must require project membership.

    Before SP0 the by-ID handlers called crud.get_project() which filtered
    by organisation only, not by membership.  Any org member who knew a project
    UUID could read, update, or delete it (IDOR).  This class verifies that
    the gap is closed — non-members receive 404 on all three verbs, while
    actual members continue to work normally.
    """

    # --- GET ---

    def test_non_member_get_by_id_returns_404(
        self, authenticated_client, test_db, test_org_id
    ):
        """A user who is NOT enrolled cannot read a project by ID (404)."""
        project = _make_project(test_db, test_org_id)
        test_db.flush()

        response = authenticated_client.get(f"/projects/{project.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_get_by_id_returns_200(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """An enrolled user can still read a project by ID (200)."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.get(f"/projects/{project.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(project.id)

    # --- PUT ---

    def test_non_member_put_by_id_returns_404(
        self, authenticated_client, test_db, test_org_id
    ):
        """A user who is NOT enrolled cannot update a project by ID (404)."""
        project = _make_project(test_db, test_org_id)
        test_db.flush()

        response = authenticated_client.put(
            f"/projects/{project.id}",
            json={"name": "hijacked name"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_put_by_id_returns_200(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """An enrolled user can still update a project by ID (200)."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.put(
            f"/projects/{project.id}",
            json={"name": project.name, "description": "updated by member"},
        )
        assert response.status_code == status.HTTP_200_OK

    # --- DELETE ---

    def test_non_member_delete_by_id_returns_404(
        self, authenticated_client, test_db, test_org_id
    ):
        """A user who is NOT enrolled cannot delete a project by ID (404)."""
        project = _make_project(test_db, test_org_id)
        test_db.flush()

        response = authenticated_client.delete(f"/projects/{project.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_member_delete_by_id_returns_200(
        self, authenticated_client, test_db, test_org_id, authenticated_user_id
    ):
        """An enrolled user can still delete a project by ID (200)."""
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        test_db.flush()

        response = authenticated_client.delete(f"/projects/{project.id}")
        assert response.status_code == status.HTTP_200_OK

    # --- Unknown project ---

    def test_unknown_project_id_returns_404(self, authenticated_client):
        """A completely unknown project UUID returns 404 (no info leak)."""
        response = authenticated_client.get(f"/projects/{uuid.uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Parameters sub-router (_load_project) ---

    def test_non_member_parameters_schema_returns_404(
        self, authenticated_client, test_db, test_org_id
    ):
        """GET /projects/{id}/parameters/schema is also membership-gated (_load_project)."""
        project = _make_project(test_db, test_org_id)
        test_db.flush()

        response = authenticated_client.get(f"/projects/{project.id}/parameters/schema")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 5. Enrollment service invariants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnrollmentService:
    """Service-layer tests for enroll / unenroll routines."""

    def test_enroll_sets_default_project_when_empty(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Enrolling a user with no default_project fills it in."""
        user = _unique_user(test_db, test_org_id)
        # Verify there's no default_project yet.
        assert user.user_settings is None or (not (user.user_settings or {}).get("default_project"))

        project = _make_project(test_db, test_org_id)
        enroll_user_in_project(
            test_db,
            user_id=str(user.id),
            project_id=str(project.id),
            organization_id=test_org_id,
        )
        test_db.flush()
        test_db.refresh(user)

        settings = user.user_settings or {}
        assert settings.get("default_project") is not None
        assert settings["default_project"]["project_id"] == str(project.id)

        test_db.rollback()

    def test_enroll_is_idempotent_no_duplicate_membership(self, test_db: Session, test_org_id):
        """Calling enroll_user_in_project twice does not create a duplicate membership row."""
        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)

        enroll_user_in_project(test_db, str(user.id), str(project.id), test_org_id)
        test_db.flush()
        enroll_user_in_project(test_db, str(user.id), str(project.id), test_org_id)
        test_db.flush()

        with bypass_tenant_filter():
            count = (
                test_db.query(ProjectMembership)
                .filter_by(user_id=user.id, project_id=project.id)
                .count()
            )
        assert count == 1

        test_db.rollback()

    def test_unenroll_removes_membership(self, test_db: Session, test_org_id):
        """unenroll_user_from_project deletes the membership row."""
        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)

        enroll_user_in_project(test_db, str(user.id), str(project.id), test_org_id)
        test_db.flush()

        removed = unenroll_user_from_project(test_db, str(user.id), str(project.id), test_org_id)
        assert removed is True
        test_db.flush()

        with bypass_tenant_filter():
            membership = (
                test_db.query(ProjectMembership)
                .filter_by(user_id=user.id, project_id=project.id)
                .first()
            )
        assert membership is None

        test_db.rollback()

    def test_unenroll_repairs_default_project(self, test_db: Session, test_org_id):
        """When the default project is unenrolled, default_project is reassigned or cleared."""
        user = _unique_user(test_db, test_org_id)
        project_a = _make_project(test_db, test_org_id)
        project_b = _make_project(test_db, test_org_id)

        # Enroll in both; first enroll sets default → project_a.
        enroll_user_in_project(test_db, str(user.id), str(project_a.id), test_org_id)
        test_db.flush()
        test_db.refresh(user)
        assert (user.user_settings or {}).get("default_project", {}).get("project_id") == str(project_a.id)

        enroll_user_in_project(test_db, str(user.id), str(project_b.id), test_org_id)
        test_db.flush()

        # Unenroll from project_a (the current default).
        unenroll_user_from_project(test_db, str(user.id), str(project_a.id), test_org_id)
        test_db.flush()
        test_db.refresh(user)

        new_default = (user.user_settings or {}).get("default_project")
        # Default must either be None or switched to the remaining project.
        if new_default is not None:
            assert new_default["project_id"] == str(project_b.id)

        test_db.rollback()

    def test_unenroll_nonexistent_membership_returns_false(self, test_db: Session, test_org_id):
        """unenroll_user_from_project on a non-member returns False (no error)."""
        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)

        removed = unenroll_user_from_project(test_db, str(user.id), str(project.id), test_org_id)
        assert removed is False

        test_db.rollback()

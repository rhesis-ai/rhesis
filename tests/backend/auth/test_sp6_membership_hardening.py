"""SP6 tests — role_id column + membership API hardening + recovery CLI.

Exit criteria:
1. ``project_membership.role_id`` column exists (nullable UUID, no FK yet).
2. GET/POST/DELETE /projects/{id}/members return 403 for a non-owner org member
   (``Permission.ProjectMember.MANAGE`` is owner-only in community tier).
3. Owner/self guards (ProjectOwnerRemovalError / ProjectSelfRemovalError) still work.
4. ``enroll_user_in_project`` accepts optional ``role_id``; persists when supplied.
5. Recovery CLI (``scripts/recover_org_owner.py``) dry-run runs end-to-end without
   errors and commits nothing; real-run reassigns ``organization.owner_id``.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_sp6_membership_hardening.py -v
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.app.services.organization import (
    ProjectOwnerRemovalError,
    ProjectSelfRemovalError,
    enroll_user_in_project,
    unenroll_user_from_project,
)
from tests.backend.fixtures.test_setup import temporarily_set_org_role

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_user(test_db: Session, org_id: str) -> models.User:
    """Create a fresh user in the test org (auto-rolled-back with the session)."""
    suffix = uuid.uuid4().hex[:10]
    user = models.User(
        email=f"sp6-test-{suffix}@rhesis-test.com",
        name=f"SP6 Test {suffix}",
        given_name="SP6",
        family_name="Test",
        is_active=True,
        auth0_id=f"auth0|sp6{suffix}",
        organization_id=org_id,
    )
    test_db.add(user)
    test_db.flush()
    test_db.refresh(user)
    return user


def _make_project(test_db: Session, org_id: str, owner_id: str | None = None) -> models.Project:
    """Create a project row directly without auto-enrollment."""
    project = models.Project(
        name=f"SP6 Test Project {uuid.uuid4().hex[:8]}",
        description="SP6 membership hardening test",
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
    enroll_user_in_project(test_db, user_id=user_id, project_id=project_id, organization_id=org_id)
    test_db.flush()


# ---------------------------------------------------------------------------
# 1. role_id column — schema / service / ORM
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoleIdColumn:
    """The project_membership table has a nullable role_id column."""

    def test_membership_model_has_role_id_attribute(self):
        """ProjectMembership ORM model exposes a role_id attribute."""
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(ProjectMembership)
        column_names = [c.key for c in mapper.columns]
        assert "role_id" in column_names, (
            "ProjectMembership must have a role_id column (SP6 EE seam)"
        )

    def test_role_id_column_is_nullable(self):
        """role_id must be nullable — binary semantics until EE (SP8) fills it."""
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(ProjectMembership)
        col = mapper.columns["role_id"]
        assert col.nullable is True, "role_id must be nullable in community tier"

    def test_enroll_user_in_project_accepts_role_id(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """enroll_user_in_project stores role_id when supplied."""
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import Role

        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)
        with bypass_tenant_filter():
            owner_role = test_db.query(Role).filter_by(name="Member", is_built_in=True).first()
        assert owner_role is not None, "Member built-in role not seeded by migrations"
        fake_role_id = owner_role.id

        enroll_user_in_project(
            test_db,
            user_id=str(user.id),
            project_id=str(project.id),
            organization_id=test_org_id,
            role_id=fake_role_id,
        )
        test_db.flush()

        with bypass_tenant_filter():
            membership = (
                test_db.query(ProjectMembership)
                .filter_by(user_id=user.id, project_id=project.id)
                .first()
            )
        assert membership is not None
        assert str(membership.role_id) == str(fake_role_id), (
            "role_id must be persisted when passed to enroll_user_in_project"
        )

        test_db.rollback()

    def test_enroll_user_in_project_default_role_id_is_none(self, test_db: Session, test_org_id):
        """enroll_user_in_project defaults role_id to None (binary mode)."""
        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)

        enroll_user_in_project(
            test_db,
            user_id=str(user.id),
            project_id=str(project.id),
            organization_id=test_org_id,
        )
        test_db.flush()

        with bypass_tenant_filter():
            membership = (
                test_db.query(ProjectMembership)
                .filter_by(user_id=user.id, project_id=project.id)
                .first()
            )
        assert membership is not None
        assert membership.role_id is None

        test_db.rollback()


# ---------------------------------------------------------------------------
# 2. Member endpoint gating — non-owner gets 403
# ---------------------------------------------------------------------------


@pytest.mark.routes
class TestMemberEndpointGating:
    """GET/POST/DELETE /projects/{id}/members require org ownership.

    In the community tier ``Permission.ProjectMember.MANAGE`` is in
    ``_OWNER_ONLY_CAPABILITIES`` and gates all three member endpoints
    (list/add/remove, plan §1.5), so any caller who is NOT the org owner
    receives 403.  The org owner continues to work normally.
    """

    # The tests temporarily strip the org's owner_id so the authenticated_client
    # user is definitively NOT an org owner for the scope of the assertion.

    # Under RBAC, project-member management is gated by the caller's role
    # (ProjectMember.MANAGE), not organization.owner_id. To represent a
    # non-privileged caller we demote the shared session user to the "None"
    # org role (no permissions) via temporarily_set_org_role; the project the
    # caller "owns" grants no capability without a role.

    def test_non_owner_cannot_list_members(
        self,
        authenticated_client,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        """GET /projects/{id}/members → 403 for a caller without ProjectMember.MANAGE."""
        project = _make_project(test_db, test_org_id, owner_id=authenticated_user_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)

        with temporarily_set_org_role(test_db, test_org_id, authenticated_user_id, "None"):
            response = authenticated_client.get(f"/projects/{project.id}/members")

        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Expected 403 for non-privileged member listing, got {response.status_code}: "
            f"{response.text}"
        )

    def test_non_owner_cannot_add_member(
        self,
        authenticated_client,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        """POST /projects/{id}/members → 403 for a caller without ProjectMember.MANAGE."""
        project = _make_project(test_db, test_org_id, owner_id=authenticated_user_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        other = _unique_user(test_db, test_org_id)

        with temporarily_set_org_role(test_db, test_org_id, authenticated_user_id, "None"):
            response = authenticated_client.post(
                f"/projects/{project.id}/members",
                json={"user_id": str(other.id)},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Expected 403 for non-privileged member management, got {response.status_code}: "
            f"{response.text}"
        )

    def test_non_owner_cannot_remove_member(
        self,
        authenticated_client,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        """DELETE /projects/{id}/members/{uid} → 403 for a caller without ProjectMember.MANAGE."""
        project = _make_project(test_db, test_org_id, owner_id=authenticated_user_id)
        other = _unique_user(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        _enroll(test_db, str(other.id), str(project.id), test_org_id)

        with temporarily_set_org_role(test_db, test_org_id, authenticated_user_id, "None"):
            response = authenticated_client.delete(f"/projects/{project.id}/members/{other.id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Expected 403 for non-privileged member removal, got {response.status_code}: "
            f"{response.text}"
        )

    def test_org_owner_can_add_member(
        self,
        authenticated_client,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        """POST /projects/{id}/members → 201 when caller IS the org owner."""
        # Ensure the caller IS the org owner (default in test fixtures, but be explicit).
        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original = org.owner_id
        org.owner_id = uuid.UUID(str(authenticated_user_id))
        test_db.flush()

        project = _make_project(test_db, test_org_id, owner_id=authenticated_user_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        other = _unique_user(test_db, test_org_id)

        try:
            response = authenticated_client.post(
                f"/projects/{project.id}/members",
                json={"user_id": str(other.id)},
            )
        finally:
            org.owner_id = original
            test_db.flush()

        assert response.status_code == status.HTTP_201_CREATED, (
            f"Org owner must be able to add members (got {response.status_code})"
        )

    def test_org_owner_can_remove_member(
        self,
        authenticated_client,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        """DELETE /projects/{id}/members/{uid} → 204 when caller IS the org owner."""
        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original = org.owner_id
        org.owner_id = uuid.UUID(str(authenticated_user_id))
        test_db.flush()

        project = _make_project(test_db, test_org_id, owner_id=authenticated_user_id)
        other = _unique_user(test_db, test_org_id)
        _enroll(test_db, str(authenticated_user_id), str(project.id), test_org_id)
        _enroll(test_db, str(other.id), str(project.id), test_org_id)

        try:
            response = authenticated_client.delete(f"/projects/{project.id}/members/{other.id}")
        finally:
            org.owner_id = original
            test_db.flush()

        assert response.status_code == status.HTTP_204_NO_CONTENT, (
            f"Org owner must be able to remove members (got {response.status_code})"
        )


# ---------------------------------------------------------------------------
# 3. Owner / self guards still fire at service layer
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOwnerAndSelfGuards:
    """ProjectOwnerRemovalError and ProjectSelfRemovalError still fire.

    These guards live in services/organization.py and must remain active
    regardless of who is calling (HTTP or direct service call).
    """

    def test_self_removal_raises(self, test_db: Session, test_org_id):
        """unenroll_user_from_project raises ProjectSelfRemovalError on self-removal."""
        user = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id)
        _enroll(test_db, str(user.id), str(project.id), test_org_id)

        with pytest.raises(ProjectSelfRemovalError):
            unenroll_user_from_project(
                test_db,
                str(user.id),
                str(project.id),
                test_org_id,
                requester_user_id=user.id,
            )

        test_db.rollback()

    def test_owner_removal_raises(self, test_db: Session, test_org_id):
        """unenroll_user_from_project raises ProjectOwnerRemovalError for project owner."""
        owner = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id, owner_id=str(owner.id))
        requester = _unique_user(test_db, test_org_id)
        _enroll(test_db, str(owner.id), str(project.id), test_org_id)
        _enroll(test_db, str(requester.id), str(project.id), test_org_id)

        with pytest.raises(ProjectOwnerRemovalError):
            unenroll_user_from_project(
                test_db,
                str(owner.id),
                str(project.id),
                test_org_id,
                requester_user_id=requester.id,
            )

        test_db.rollback()

    def test_non_owner_member_can_be_removed_by_service(self, test_db: Session, test_org_id):
        """A regular (non-owner) member can be unenrolled via the service layer."""
        owner = _unique_user(test_db, test_org_id)
        member = _unique_user(test_db, test_org_id)
        project = _make_project(test_db, test_org_id, owner_id=str(owner.id))
        _enroll(test_db, str(owner.id), str(project.id), test_org_id)
        _enroll(test_db, str(member.id), str(project.id), test_org_id)

        removed = unenroll_user_from_project(
            test_db,
            str(member.id),
            str(project.id),
            test_org_id,
            requester_user_id=owner.id,
        )
        assert removed is True

        test_db.rollback()


# ---------------------------------------------------------------------------
# 4. Recovery CLI dry-run
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecoverOrgOwnerCLI:
    """Break-glass recovery CLI (scripts/recover_org_owner.py).

    Tests call the ``run()`` function directly to stay in-process and share
    the test database, avoiding subprocess overhead.
    """

    def test_dry_run_does_not_mutate_owner(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """dry_run=True prints intent and rolls back — owner_id unchanged."""
        from rhesis.backend.app.management.recover_org_owner import run

        # Create a second user to be the "new owner" in dry-run mode.
        new_owner = _unique_user(test_db, test_org_id)
        test_db.commit()  # commit so the CLI's independent session can see it

        org_before = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        owner_before = org_before.owner_id

        # Dry run should complete without raising.
        run(str(test_org_id), str(new_owner.id), dry_run=True)

        # Re-query to verify the owner_id was NOT changed.
        test_db.expire(org_before)
        org_after = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        assert org_after.owner_id == owner_before, (
            "dry_run=True must not mutate organization.owner_id"
        )

    def test_real_run_reassigns_owner(self, test_db: Session, test_org_id, authenticated_user_id):
        """dry_run=False reassigns organization.owner_id to the target user."""
        from rhesis.backend.app.management.recover_org_owner import run

        new_owner = _unique_user(test_db, test_org_id)
        test_db.commit()

        org = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        original_owner = org.owner_id

        run(str(test_org_id), str(new_owner.id), dry_run=False)

        # The CLI uses its own session (SessionLocal), so expire the fixture session
        # and re-read to see the committed change.
        test_db.expire_all()
        org_after = test_db.query(models.Organization).filter_by(id=test_org_id).first()
        assert str(org_after.owner_id) == str(new_owner.id), (
            "real run must update organization.owner_id to the new owner"
        )

        # Restore the original owner so subsequent tests keep the expected context.
        org_after.owner_id = original_owner
        test_db.commit()

    def test_run_rejects_unknown_org(self):
        """run() exits with SystemExit when the org UUID does not exist."""
        from rhesis.backend.app.management.recover_org_owner import run

        with pytest.raises(SystemExit):
            run(str(uuid.uuid4()), str(uuid.uuid4()))

    def test_run_rejects_user_not_in_org(self, test_org_id):
        """run() exits when the target user does not belong to the org."""
        from rhesis.backend.app.management.recover_org_owner import run

        with pytest.raises(SystemExit):
            run(str(test_org_id), str(uuid.uuid4()))  # UUID not in org

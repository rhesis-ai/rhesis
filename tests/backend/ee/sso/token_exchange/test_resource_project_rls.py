"""``_resolve_resource_project`` must work for an app role subject to RLS.

``project`` and ``project_membership`` are both FORCE ROW LEVEL SECURITY with a
strict ``organization_id = current_setting('app.current_organization')::uuid``
policy and no empty-org passthrough (unlike ``organization``). The exchange runs
on ``get_db_session``, which binds no tenant GUCs, so the resource lookup has to
bind org scope itself or it raises ``invalid input syntax for type uuid: ""``.

The test suite now runs as a non-BYPASSRLS role (``rhesis-app``), so RLS is
enforced by default. These tests blank the org GUC to simulate the unscoped
session ``get_db_session`` provides.
"""

import uuid as _uuid

import pytest
from sqlalchemy import text

from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.ee.sso.token_exchange.exchange import _resolve_resource_project


@pytest.mark.integration
class TestResolveResourceProjectUnderEnforcedRLS:
    def _make_project(self, test_db, test_organization, db_user, db_owner_user, db_status):
        project = Project(
            name=f"Resource RLS {_uuid.uuid4().hex[:6]}",
            is_active=True,
            user_id=db_user.id,
            owner_id=db_owner_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(project)
        test_db.flush()
        return project

    def _blank_org_guc(self, test_db):
        """Blank the org GUC to simulate an unscoped get_db_session."""
        test_db.execute(text("SET LOCAL app.current_organization = ''"))

    def test_resolves_member_project(
        self, test_db, test_organization, db_user, db_owner_user, db_status
    ):
        project = self._make_project(test_db, test_organization, db_user, db_owner_user, db_status)
        test_db.add(
            ProjectMembership(
                project_id=project.id,
                user_id=db_user.id,
                organization_id=test_organization.id,
            )
        )
        test_db.flush()
        project_id = str(project.id)

        self._blank_org_guc(test_db)
        found, is_member = _resolve_resource_project(
            test_db, test_organization, db_user, project_id
        )

        assert found is not None, (
            "project invisible to an RLS-enforced role -- the org scope binding "
            "in _resolve_resource_project regressed"
        )
        assert str(found.id) == project_id
        assert is_member is True

    def test_non_member_project_resolves_but_is_not_member(
        self, test_db, test_organization, db_user, db_owner_user, db_status
    ):
        """No ProjectMembership row -> found, but is_member False (a deny)."""
        project = self._make_project(test_db, test_organization, db_user, db_owner_user, db_status)
        test_db.flush()

        self._blank_org_guc(test_db)
        found, is_member = _resolve_resource_project(
            test_db, test_organization, db_user, str(project.id)
        )

        assert found is not None
        assert is_member is False

    def test_unknown_project_returns_none(
        self, test_db, test_organization, db_user, db_owner_user, db_status
    ):
        self._blank_org_guc(test_db)
        found, is_member = _resolve_resource_project(
            test_db, test_organization, db_user, str(_uuid.uuid4())
        )

        assert found is None
        assert is_member is False

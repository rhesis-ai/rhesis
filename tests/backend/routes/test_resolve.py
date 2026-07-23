"""Tests for cross-project entity resolution."""

import pytest
from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.dependencies import get_project_context
from rhesis.backend.app.main import app
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.routers.resolve import get_resolvable_entities

fake = Faker()


def _override_active_project(project_id: str):
    def _dependency():
        return project_id

    return _dependency


@pytest.fixture
def active_project_context(db_project):
    """Pin the active project for resolve endpoint tests."""
    app.dependency_overrides[get_project_context] = _override_active_project(str(db_project.id))
    yield db_project
    app.dependency_overrides.pop(get_project_context, None)


class TestResolvableEntities:
    def test_includes_project_scoped_models(self):
        entities = get_resolvable_entities()
        assert "test_set" in entities
        assert "endpoint" in entities
        assert entities["test_set"].__tablename__ == "test_set"


@pytest.mark.integration
class TestResolveEntityEndpoint:
    def _create_project_with_membership(
        self,
        test_db,
        test_organization,
        db_user,
        db_owner_user,
        db_status,
        user_id,
        name_suffix: str,
    ) -> Project:
        project = Project(
            name=f"Resolve Project {name_suffix}",
            description=fake.text(max_nb_chars=100),
            icon="🧪",
            is_active=True,
            user_id=db_user.id,
            owner_id=db_owner_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(project)
        test_db.flush()

        test_db.add(
            ProjectMembership(
                project_id=project.id,
                user_id=user_id,
                organization_id=test_organization.id,
            )
        )
        test_db.flush()
        test_db.refresh(project)
        return project

    def test_switchable_when_entity_in_other_project(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_owner_user,
        db_status,
        active_project_context,
        authenticated_user_id,
    ):
        other_project = self._create_project_with_membership(
            test_db,
            test_organization,
            db_user,
            db_owner_user,
            db_status,
            authenticated_user_id,
            "other",
        )

        test_set = TestSet(
            name="Cross-project test set",
            description="Belongs to another project",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            project_id=other_project.id,
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.flush()

        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "test_set",
                "entity_id": str(test_set.id),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resolution"] == "switchable"
        assert data["project_id"] == str(other_project.id)
        assert data["project_name"] == other_project.name

    def test_archived_project_not_offered_as_switchable(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_owner_user,
        db_status,
        active_project_context,
        authenticated_user_id,
    ):
        """An entity in a project the caller is a member of, but the project is
        inactive/archived, must not be offered as a switch target — it should
        404 like any other project the candidate list excludes."""
        archived_project = self._create_project_with_membership(
            test_db,
            test_organization,
            db_user,
            db_owner_user,
            db_status,
            authenticated_user_id,
            "archived",
        )
        archived_project.is_active = False
        test_db.flush()

        test_set = TestSet(
            name="Archived-project test set",
            description="Belongs to an archived project",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            project_id=archived_project.id,
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.flush()

        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "test_set",
                "entity_id": str(test_set.id),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_member_of_entity_project_returns_404(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_owner_user,
        db_status,
        active_project_context,
    ):
        """Entity in a project the caller is NOT a member of resolves to 404.

        The caller can only probe projects they belong to, so a project they
        cannot access is indistinguishable from a non-existent one — there is no
        ``no_access`` outcome, and its existence is not revealed.
        """
        foreign_project = Project(
            name="Resolve Project Foreign",
            description=fake.text(max_nb_chars=100),
            icon="🚫",
            is_active=True,
            user_id=db_user.id,
            owner_id=db_owner_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(foreign_project)
        test_db.flush()

        test_set = TestSet(
            name="Foreign-project test set",
            description="In a project the caller cannot access",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            project_id=foreign_project.id,
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.flush()

        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "test_set",
                "entity_id": str(test_set.id),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_same_project_returns_404(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        db_user,
        db_status,
        active_project_context,
    ):
        db_project = active_project_context
        test_set = TestSet(
            name="Same-project test set",
            description="Visible in active project",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            project_id=db_project.id,
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.flush()

        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "test_set",
                "entity_id": str(test_set.id),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_entity_type_returns_400(self, authenticated_client: TestClient):
        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "not_a_real_table",
                "entity_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_detail_entity_type_returns_400(self, authenticated_client: TestClient):
        """Internal project-scoped tables without detail pages are not resolvable."""
        entities = get_resolvable_entities()
        assert "comment" not in entities

        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "comment",
                "entity_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_entity_returns_404(self, authenticated_client: TestClient):
        response = authenticated_client.get(
            "/resolve",
            params={
                "entity_type": "test_set",
                "entity_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestResolveUnderEnforcedRLS:
    """Guard the premise the resolve endpoint relies on: a project-scoped row is
    visible only when ``app.current_project`` matches the row's project.

    This exercises real Postgres RLS via a non-BYPASSRLS role, the production
    scenario. The normal test DB role is a superuser that bypasses RLS entirely
    — which is exactly why the original ``bypass_tenant_filter()`` approach
    (ORM-level only) passed tests yet returned 404 in production, where the app
    role is subject to ``FORCE ROW LEVEL SECURITY``. Because the endpoint's
    probe runs on the superuser app session, this asserts the RLS behavior at
    the query layer rather than through the endpoint.
    """

    def _make_project(self, test_db, test_organization, db_user, db_owner_user, db_status, name):
        project = Project(
            name=name,
            description=fake.text(max_nb_chars=60),
            icon="🔒",
            is_active=True,
            user_id=db_user.id,
            owner_id=db_owner_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(project)
        test_db.flush()
        return project

    def test_entity_visible_only_under_its_own_project_scope(
        self,
        test_db,
        test_organization,
        db_user,
        db_owner_user,
        db_status,
    ):
        import uuid as _uuid

        from sqlalchemy import text

        org_id = str(test_organization.id)

        project_a = self._make_project(
            test_db, test_organization, db_user, db_owner_user, db_status, "RLS Project A"
        )
        project_b = self._make_project(
            test_db, test_organization, db_user, db_owner_user, db_status, "RLS Project B"
        )

        test_set = TestSet(
            name="RLS cross-project test set",
            description="Lives in project B",
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            project_id=project_b.id,
            is_published=False,
            visibility="organization",
        )
        test_db.add(test_set)
        test_db.flush()

        entity_id = str(test_set.id)
        probe = f"resolve_rls_probe_{_uuid.uuid4().hex[:8]}"

        test_db.execute(text(f'CREATE ROLE "{probe}" NOLOGIN'))
        test_db.execute(text(f'GRANT SELECT ON public.test_set TO "{probe}"'))
        test_db.execute(text(f'SET LOCAL ROLE "{probe}"'))
        test_db.execute(text("SET LOCAL app.current_organization = :o"), {"o": org_id})

        # Scoped to the WRONG project: RLS hides the row. This is the failure the
        # old ORM-only bypass could not avoid — the app role never sees it.
        test_db.execute(text("SET LOCAL app.current_project = :p"), {"p": str(project_a.id)})
        wrong_scope = test_db.execute(
            text("SELECT id FROM test_set WHERE id = :id"), {"id": entity_id}
        ).fetchone()
        assert wrong_scope is None, (
            "cross-project entity was visible under the wrong project scope — "
            "RLS project_isolation is not enforcing"
        )

        # Scoped to the entity's OWN project: RLS admits the row. This is what
        # the per-project probe depends on.
        test_db.execute(text("SET LOCAL app.current_project = :p"), {"p": str(project_b.id)})
        right_scope = test_db.execute(
            text("SELECT id FROM test_set WHERE id = :id"), {"id": entity_id}
        ).fetchone()
        assert right_scope is not None, (
            "entity hidden even under its own project scope — the probe would never find it"
        )

        test_db.execute(text("RESET ROLE"))

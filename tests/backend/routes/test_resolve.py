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
    app.dependency_overrides[get_project_context] = _override_active_project(
        str(db_project.id)
    )
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

"""``get_requirement_descriptions`` against a real database."""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.requirement import get_requirement_descriptions
from rhesis.backend.app.services.generation import requirement_descriptions_in_project
from rhesis.backend.app.utils import crud_utils
from tests.backend.fixtures.rls import scope_to_project


def _requirement(db: Session, org_id, name: str, description, project_id=None):
    return crud_utils.create_item(
        db,
        models.Requirement,
        {"name": name, "description": description, "project_id": project_id},
        organization_id=org_id,
    )


def _project(db: Session, org_id, user_id) -> models.Project:
    project = models.Project(name="Visit-Prep", organization_id=org_id, user_id=user_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.mark.integration
class TestGetRequirementDescriptions:
    def test_returns_descriptions_by_exact_name(self, test_db: Session, test_org_id):
        _requirement(test_db, test_org_id, "R1: Never diagnoses", "No reply names a condition.")
        _requirement(test_db, test_org_id, "R2: Never recommends treatment", "No medication.")

        result = get_requirement_descriptions(test_db, ["R1: Never diagnoses", "Unknown"])

        assert result == {"R1: Never diagnoses": "No reply names a condition."}

    def test_skips_requirements_without_a_description(self, test_db: Session, test_org_id):
        _requirement(test_db, test_org_id, "No description", None)
        _requirement(test_db, test_org_id, "Empty description", "")

        assert get_requirement_descriptions(test_db, ["No description", "Empty description"]) == {}

    def test_no_names_reads_nothing(self, test_db: Session):
        assert get_requirement_descriptions(test_db, []) == {}

    def test_project_requirement_wins_over_an_org_level_one_with_the_same_name(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        project = _project(test_db, test_org_id, authenticated_user_id)
        scope_to_project(test_db, project.id)
        _requirement(test_db, test_org_id, "Shared name", "Project criteria", project.id)
        _requirement(test_db, test_org_id, "Shared name", "Org criteria")

        assert get_requirement_descriptions(test_db, ["Shared name"]) == {
            "Shared name": "Project criteria"
        }


@pytest.mark.integration
class TestRequirementDescriptionsInProject:
    def test_finds_project_requirements_the_unscoped_session_cannot_see(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        project = _project(test_db, test_org_id, authenticated_user_id)
        scope_to_project(test_db, project.id)
        _requirement(test_db, test_org_id, "R1", "Project criteria", project.id)
        test_db.commit()
        scope_to_project(test_db, None)

        # What a session without the project bound sees: nothing.
        assert get_requirement_descriptions(test_db, ["R1"]) == {}
        assert requirement_descriptions_in_project(
            test_db, test_org_id, authenticated_user_id, str(project.id), ["R1"]
        ) == {"R1": "Project criteria"}

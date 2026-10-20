"""``get_requirement_descriptions`` against a real database."""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.requirement import get_requirement_descriptions
from rhesis.backend.app.utils import crud_utils


def _requirement(db: Session, org_id, name: str, description):
    return crud_utils.create_item(
        db,
        models.Requirement,
        {"name": name, "description": description},
        organization_id=org_id,
    )


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

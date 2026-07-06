"""
🧪 Test CRUD Operations Testing

Comprehensive test suite for test entity CRUD operations.
Tests focus on test management operations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- delete_test: Delete test entities
- update_test: Update test entities and refresh test set attributes

Run with: python -m pytest tests/backend/crud/test_test_crud.py -v
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.constants import ADAPTIVE_TESTING_BEHAVIOR
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services import test_set as test_set_service


@pytest.mark.unit
@pytest.mark.crud
class TestTestOperations:
    """🧪 Test test operations"""

    def test_delete_test_success(
        self, test_db: Session, db_test_minimal, test_org_id: str, authenticated_user_id: str
    ):
        """Test successful test deletion"""
        # Use existing database fixture for a minimal test entity
        db_test = db_test_minimal
        test_id = db_test.id

        # Test deletion - no mocking needed, test real behavior
        result = crud.delete_test(
            db=test_db, test_id=test_id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        # Verify test was deleted
        assert result is not None
        assert result.id == test_id

        # Verify test is deleted from database
        deleted_test = test_db.query(models.Test).filter(models.Test.id == test_id).first()
        assert deleted_test is None

    def test_delete_test_not_found(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Test deletion of non-existent test"""
        fake_test_id = uuid.uuid4()

        result = crud.delete_test(
            db=test_db,
            test_id=fake_test_id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Should return None for non-existent test
        assert result is None

    def test_update_test_refreshes_test_set_attributes_on_behavior_change(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Updating test behavior refreshes linked test set denormalized attributes."""
        compliance = models.Behavior(
            name="Compliance",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        robustness = models.Behavior(
            name="Robustness",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([compliance, robustness])
        test_db.flush()

        db_test = models.Test(
            behavior_id=compliance.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_set = models.TestSet(
            name="Linked Attributes Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([db_test, test_set])
        test_db.flush()

        test_db.execute(
            test_test_set_association.insert().values(
                test_id=db_test.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.flush()

        test_set_service.update_test_set_attributes(
            db=test_db,
            test_set_id=str(test_set.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.refresh(test_set)
        assert test_set.attributes["metadata"]["behaviors"] == ["Compliance"]

        result = crud.update_test(
            db=test_db,
            test_id=db_test.id,
            test={"behavior_id": robustness.id},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is not None
        assert result.behavior_id == robustness.id

        reloaded_test_set = crud.get_test_set(
            test_db,
            test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert reloaded_test_set is not None
        assert reloaded_test_set.attributes["metadata"]["behaviors"] == ["Robustness"]

    def test_update_test_skips_attribute_refresh_for_non_metadata_fields(
        self, test_db: Session, db_test_minimal, test_org_id: str, authenticated_user_id: str
    ):
        """Non-metadata updates should not trigger test set attribute regeneration."""
        with patch(
            "rhesis.backend.app.services.test_set.update_test_set_attributes"
        ) as mock_refresh:
            result = crud.update_test(
                db=test_db,
                test_id=db_test_minimal.id,
                test={"priority": 3},
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )

        assert result is not None
        mock_refresh.assert_not_called()

    def test_update_test_skips_explorer_test_set_attribute_refresh(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        """Explorer test sets keep their own attributes when a linked test changes."""
        compliance = models.Behavior(
            name="Compliance",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        robustness = models.Behavior(
            name="Robustness",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([compliance, robustness])
        test_db.flush()

        db_test = models.Test(
            behavior_id=compliance.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        explorer_test_set = models.TestSet(
            name="Explorer Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            attributes={"metadata": {"behaviors": [ADAPTIVE_TESTING_BEHAVIOR]}},
        )
        test_db.add_all([db_test, explorer_test_set])
        test_db.flush()

        test_db.execute(
            test_test_set_association.insert().values(
                test_id=db_test.id,
                test_set_id=explorer_test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.flush()

        crud.update_test(
            db=test_db,
            test_id=db_test.id,
            test={"behavior_id": robustness.id},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        reloaded_explorer_test_set = crud.get_test_set(
            test_db,
            explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        assert reloaded_explorer_test_set is not None
        assert reloaded_explorer_test_set.attributes["metadata"]["behaviors"] == [
            ADAPTIVE_TESTING_BEHAVIOR
        ]

"""
🧪 Test CRUD Operations Testing

Comprehensive test suite for test entity CRUD operations.
Tests focus on test management operations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- delete_test: Delete test entities

Run with: python -m pytest tests/backend/crud/test_test_crud.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models


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

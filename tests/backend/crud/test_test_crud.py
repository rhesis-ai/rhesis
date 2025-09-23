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
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models


@pytest.mark.unit
@pytest.mark.crud
class TestTestOperations:
    """🧪 Test test operations"""
    
    def test_delete_test_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str, crud_factory):
        """Test successful test deletion"""
        # Create a simple test without associations to avoid foreign key issues
        test_data = crud_factory.create_test_data(test_org_id, authenticated_user_id)
        db_test = models.Test(**test_data)
        test_db.add(db_test)
        test_db.flush()
        
        # Mock the update_test_set_attributes function  
        with patch('rhesis.backend.app.services.test_set.update_test_set_attributes') as mock_update:
            # Store test ID for later verification
            test_id = db_test.id
            
            # Test deletion
            result = crud.delete_test(db=test_db, test_id=test_id)
            
            # Verify test was deleted
            assert result is not None
            assert result.id == test_id
            
            # Verify test is deleted from database
            deleted_test = test_db.query(models.Test).filter(models.Test.id == test_id).first()
            assert deleted_test is None
            
            # Since there were no associations, update_test_set_attributes should not be called
            assert mock_update.call_count == 0
    
    def test_delete_test_not_found(self, test_db: Session):
        """Test deletion of non-existent test"""
        fake_test_id = uuid.uuid4()
        
        result = crud.delete_test(db=test_db, test_id=fake_test_id)
        
        # Should return None for non-existent test
        assert result is None

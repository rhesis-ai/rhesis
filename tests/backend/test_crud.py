"""
🗄️ CRUD Operations Testing Suite

Comprehensive test suite for crud.py functions.
These tests focus on the business logic of CRUD operations while ensuring proper tenant
isolation and data integrity.

Functions tested:
- Tag operations: assign_tag, remove_tag
- Token operations: revoke_user_tokens  
- Test operations: delete_test
- Metric operations: get_metric, get_metrics, add_behavior_to_metric, remove_behavior_from_metric

Run with: python -m pytest tests/backend/test_crud.py -v
"""

import uuid
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.models.test import test_test_set_association

# Initialize Faker with consistent seed
fake = Faker()
Faker.seed(12345)


class CrudTestDataFactory:
    """Factory for creating test data that follows backend conventions"""
    
    @staticmethod
    def create_tag_data(org_id: str, user_id: str) -> Dict[str, Any]:
        """Create realistic tag data"""
        return {
            "name": fake.slug(),
            "icon_unicode": fake.random_element(["🏷️", "📌", "🔖", "⭐", "🎯"]),
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }
    
    @staticmethod
    def create_prompt_data(org_id: str, user_id: str) -> Dict[str, Any]:
        """Create realistic prompt data"""
        return {
            "content": fake.text(max_nb_chars=200),
            "language_code": "en-US",
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }
    
    @staticmethod
    def create_token_data(org_id: str, user_id: str, token_suffix: str = "") -> Dict[str, Any]:
        """Create realistic token data"""
        return {
            "token": f"rh-{fake.lexify('????????')}{token_suffix}",
            "token_type": fake.random_element(["api", "session", "refresh"]),
            "name": f"Test Token {token_suffix}",
            "user_id": uuid.UUID(user_id),
            "organization_id": uuid.UUID(org_id)
        }
    
    @staticmethod
    def create_test_set_data(org_id: str, user_id: str, name_suffix: str = "") -> Dict[str, Any]:
        """Create realistic test set data"""
        return {
            "name": f"{fake.catch_phrase()} {name_suffix}".strip(),
            "description": fake.text(max_nb_chars=150),
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }
    
    @staticmethod
    def create_test_data(org_id: str, user_id: str) -> Dict[str, Any]:
        """Create realistic test data"""
        return {
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }
    
    @staticmethod
    def create_metric_data(org_id: str, user_id: str, name_suffix: str = "") -> Dict[str, Any]:
        """Create realistic metric data"""
        return {
            "name": f"{fake.word().title()} {fake.word().title()} {name_suffix}".strip(),
            "description": fake.text(max_nb_chars=150),
            "evaluation_prompt": fake.sentence(nb_words=8),
            "score_type": fake.random_element(["numeric", "categorical", "binary"]),
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }
    
    @staticmethod
    def create_behavior_data(org_id: str, user_id: str, name_suffix: str = "") -> Dict[str, Any]:
        """Create realistic behavior data"""
        return {
            "name": f"{fake.catch_phrase()} {name_suffix}".strip(),
            "description": fake.text(max_nb_chars=100),
            "organization_id": uuid.UUID(org_id),
            "user_id": uuid.UUID(user_id)
        }


@pytest.mark.unit
@pytest.mark.crud
class TestTagOperations:
    """🏷️ Test tag CRUD operations"""
    
    def test_assign_tag_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful tag assignment to entity"""
        # Create test entity using factory
        entity_data = CrudTestDataFactory.create_prompt_data(test_org_id, authenticated_user_id)
        db_entity = models.Prompt(**entity_data)
        test_db.add(db_entity)
        test_db.flush()
        
        # Create tag schema for assignment
        tag_create_schema = schemas.TagCreate(
            name=fake.slug(),
            icon_unicode="🏷️",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id)
        )
        
        # Test tag assignment
        result = crud.assign_tag(
            db=test_db,
            tag=tag_create_schema,
            entity_id=db_entity.id,
            entity_type=EntityType.PROMPT
        )
        
        # Verify the result
        assert result is not None
        assert result.name == tag_create_schema.name
        assert result.organization_id == uuid.UUID(test_org_id)
        
        # Verify tagged_item relationship was created
        tagged_item = test_db.query(models.TaggedItem).filter(
            models.TaggedItem.tag_id == result.id,
            models.TaggedItem.entity_id == db_entity.id,
            models.TaggedItem.entity_type == EntityType.PROMPT.value
        ).first()
        
        assert tagged_item is not None
        assert tagged_item.organization_id == uuid.UUID(test_org_id)
        assert tagged_item.user_id == uuid.UUID(authenticated_user_id)
    
    def test_assign_tag_entity_not_found(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test tag assignment fails with non-existent entity"""
        fake_entity_id = uuid.uuid4()
        
        tag_create_schema = schemas.TagCreate(
            name=fake.slug(),
            icon_unicode="🏷️",
            organization_id=uuid.UUID(test_org_id),
            user_id=uuid.UUID(authenticated_user_id)
        )
        
        with pytest.raises(ValueError, match="Prompt with id .* not found"):
            crud.assign_tag(
                db=test_db,
                tag=tag_create_schema,
                entity_id=fake_entity_id,
                entity_type=EntityType.PROMPT
            )
    
    def test_remove_tag_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful tag removal from entity"""
        # Create entities using factory
        tag_data = CrudTestDataFactory.create_tag_data(test_org_id, authenticated_user_id)
        entity_data = CrudTestDataFactory.create_prompt_data(test_org_id, authenticated_user_id)
        
        db_tag = models.Tag(**tag_data)
        db_entity = models.Prompt(**entity_data)
        test_db.add_all([db_tag, db_entity])
        test_db.flush()
        
        # Create tagged_item relationship
        tagged_item_data = {
            "tag_id": db_tag.id,
            "entity_id": db_entity.id,
            "entity_type": EntityType.PROMPT.value,
            "organization_id": uuid.UUID(test_org_id),
            "user_id": uuid.UUID(authenticated_user_id)
        }
        db_tagged_item = models.TaggedItem(**tagged_item_data)
        test_db.add(db_tagged_item)
        test_db.flush()
        
        # Test tag removal
        result = crud.remove_tag(
            db=test_db,
            tag_id=db_tag.id,
            entity_id=db_entity.id,
            entity_type=EntityType.PROMPT
        )
        
        # Verify removal was successful
        assert result is True
        
        # Verify tagged_item was deleted
        tagged_item = test_db.query(models.TaggedItem).filter(
            models.TaggedItem.tag_id == db_tag.id,
            models.TaggedItem.entity_id == db_entity.id
        ).first()
        assert tagged_item is None
    
    def test_remove_tag_not_found(self, test_db: Session):
        """Test tag removal fails with non-existent tag"""
        fake_tag_id = uuid.uuid4()
        fake_entity_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Tag not found"):
            crud.remove_tag(
                db=test_db,
                tag_id=fake_tag_id,
                entity_id=fake_entity_id,
                entity_type=EntityType.PROMPT
            )


@pytest.mark.unit
@pytest.mark.crud
class TestTokenOperations:
    """🔑 Test token operations"""
    
    def test_revoke_user_tokens_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful token revocation for user"""
        user_uuid = uuid.UUID(authenticated_user_id)
        
        # Create test tokens using factory
        token_data_1 = CrudTestDataFactory.create_token_data(test_org_id, authenticated_user_id, "1")
        token_data_2 = CrudTestDataFactory.create_token_data(test_org_id, authenticated_user_id, "2")
        
        db_token_1 = models.Token(**token_data_1)
        db_token_2 = models.Token(**token_data_2)
        test_db.add_all([db_token_1, db_token_2])
        test_db.flush()
        
        # Count tokens before revocation
        tokens_before = test_db.query(models.Token).filter(
            models.Token.user_id == user_uuid
        ).count()
        
        # Test token revocation
        result = crud.revoke_user_tokens(db=test_db, user_id=user_uuid)
        
        # Verify tokens were revoked (result is count of deleted tokens)
        assert result == tokens_before
        assert tokens_before >= 2  # At least our 2 test tokens
        
        # Verify target user's tokens are deleted
        remaining_tokens = test_db.query(models.Token).filter(
            models.Token.user_id == user_uuid
        ).all()
        assert len(remaining_tokens) == 0
    
    def test_revoke_user_tokens_no_tokens(self, test_db: Session):
        """Test token revocation for user with no tokens"""
        user_id = uuid.uuid4()
        
        result = crud.revoke_user_tokens(db=test_db, user_id=user_id)
        
        # Should return 0 for no tokens revoked
        assert result == 0


@pytest.mark.unit
@pytest.mark.crud
class TestTestOperations:
    """🧪 Test test operations"""
    
    def test_delete_test_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful test deletion"""
        # Create a simple test without associations to avoid foreign key issues
        test_data = CrudTestDataFactory.create_test_data(test_org_id, authenticated_user_id)
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


@pytest.mark.unit
@pytest.mark.crud  
class TestMetricOperations:
    """📊 Test metric operations"""
    
    def test_get_metric_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful metric retrieval with relationships"""
        # Create metric using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()
        
        # Test metric retrieval
        result = crud.get_metric(db=test_db, metric_id=db_metric.id)
        
        # Verify result
        assert result is not None
        assert result.id == db_metric.id
        assert result.name == metric_data["name"]
        assert result.organization_id == uuid.UUID(test_org_id)
    
    def test_get_metric_not_found(self, test_db: Session):
        """Test metric retrieval with non-existent ID"""
        fake_metric_id = uuid.uuid4()
        
        result = crud.get_metric(db=test_db, metric_id=fake_metric_id)
        
        # Should return None for non-existent metric
        assert result is None
    
    def test_get_metrics_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful metrics listing"""
        # Create multiple metrics using factory
        metric_data_1 = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id, "Alpha")
        metric_data_2 = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id, "Beta")
        
        db_metric_1 = models.Metric(**metric_data_1)
        db_metric_2 = models.Metric(**metric_data_2)
        test_db.add_all([db_metric_1, db_metric_2])
        test_db.flush()
        
        # Test metrics listing
        result = crud.get_metrics(db=test_db, skip=0, limit=10)
        
        # Verify results
        assert len(result) >= 2  # May include other metrics from fixtures
        metric_names = [metric.name for metric in result]
        assert metric_data_1["name"] in metric_names
        assert metric_data_2["name"] in metric_names
    
    def test_add_behavior_to_metric_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful behavior addition to metric"""
        # Create metric and behavior using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        behavior_data = CrudTestDataFactory.create_behavior_data(test_org_id, authenticated_user_id)
        
        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()
        
        # Test adding behavior to metric
        result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id
        )
        
        # Verify association was created
        assert result is True
        
        # Verify association exists in database
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric.id,
                models.behavior_metric_association.c.behavior_id == db_behavior.id
            )
        ).first()
        
        assert association is not None
        assert association.organization_id == uuid.UUID(test_org_id)
    
    def test_add_behavior_to_metric_duplicate(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test adding duplicate behavior to metric"""
        # Create metric and behavior using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        behavior_data = CrudTestDataFactory.create_behavior_data(test_org_id, authenticated_user_id)
        
        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()
        
        # Add behavior to metric first time
        first_result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id
        )
        assert first_result is True
        
        # Try to add same behavior again
        second_result = crud.add_behavior_to_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id),
            user_id=authenticated_user_id
        )
        
        # Should return False for duplicate
        assert second_result is False
    
    def test_remove_behavior_from_metric_success(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test successful behavior removal from metric"""
        # Create metric and behavior using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        behavior_data = CrudTestDataFactory.create_behavior_data(test_org_id, authenticated_user_id)
        
        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()
        
        # Add behavior to metric first
        test_db.execute(
            models.behavior_metric_association.insert().values(
                metric_id=db_metric.id,
                behavior_id=db_behavior.id,
                organization_id=uuid.UUID(test_org_id),
                user_id=uuid.UUID(authenticated_user_id)
            )
        )
        test_db.flush()
        
        # Test removing behavior from metric
        result = crud.remove_behavior_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id)
        )
        
        # Verify removal was successful
        assert result is True
        
        # Verify association is deleted
        association = test_db.execute(
            models.behavior_metric_association.select().where(
                models.behavior_metric_association.c.metric_id == db_metric.id,
                models.behavior_metric_association.c.behavior_id == db_behavior.id
            )
        ).first()
        
        assert association is None
    
    def test_remove_behavior_from_metric_not_found(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test behavior removal with non-existent association"""
        # Create metric and behavior but no association using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        behavior_data = CrudTestDataFactory.create_behavior_data(test_org_id, authenticated_user_id)
        
        db_metric = models.Metric(**metric_data)
        db_behavior = models.Behavior(**behavior_data)
        test_db.add_all([db_metric, db_behavior])
        test_db.flush()
        
        # Test removing non-existent association
        result = crud.remove_behavior_from_metric(
            db=test_db,
            metric_id=db_metric.id,
            behavior_id=db_behavior.id,
            organization_id=uuid.UUID(test_org_id)
        )
        
        # Should return False for non-existent association
        assert result is False
    
    def test_remove_behavior_from_metric_invalid_metric(self, test_db: Session, test_org_id: str):
        """Test behavior removal with non-existent metric"""
        fake_metric_id = uuid.uuid4()
        fake_behavior_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Metric with id .* not found"):
            crud.remove_behavior_from_metric(
                db=test_db,
                metric_id=fake_metric_id,
                behavior_id=fake_behavior_id,
                organization_id=uuid.UUID(test_org_id)
            )
    
    def test_remove_behavior_from_metric_invalid_behavior(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        """Test behavior removal with non-existent behavior"""
        # Create metric using factory
        metric_data = CrudTestDataFactory.create_metric_data(test_org_id, authenticated_user_id)
        db_metric = models.Metric(**metric_data)
        test_db.add(db_metric)
        test_db.flush()
        
        fake_behavior_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Behavior with id .* not found"):
            crud.remove_behavior_from_metric(
                db=test_db,
                metric_id=db_metric.id,
                behavior_id=fake_behavior_id,
                organization_id=uuid.UUID(test_org_id)
            )
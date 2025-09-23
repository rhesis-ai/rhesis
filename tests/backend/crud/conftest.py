"""
🔧 CRUD Test Fixtures

Shared fixtures and utilities for CRUD operation testing.
"""

import uuid
from typing import Dict, Any

import pytest
from faker import Faker

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


@pytest.fixture
def crud_factory():
    """Provide access to the CRUD test data factory"""
    return CrudTestDataFactory

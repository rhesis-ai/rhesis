"""
📊 Data Factory System for Consistent Test Data Generation

This module provides consistent, realistic test data generation using the Faker library.
It replaces the mixed approach of faker_utils.py with a unified factory system.

Usage:
    # Standard data
    data = BehaviorDataFactory.sample_data()
    
    # Edge cases
    data = BehaviorDataFactory.edge_case_data("long_name")
    
    # Custom variations
    data = BehaviorDataFactory.sample_data(name_length=50, include_description=False)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from faker import Faker
import uuid

# Initialize Faker with consistent seed for reproducible tests
fake = Faker()
Faker.seed(12345)


class BaseDataFactory(ABC):
    """
    Abstract base class for test data factories
    
    Provides consistent interface for generating test data across all entities.
    Each entity should have its own factory that inherits from this base.
    """
    
    @classmethod
    @abstractmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal required data for entity creation"""
        pass
    
    @classmethod
    @abstractmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample data with common optional fields"""
        pass
    
    @classmethod
    @abstractmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate data suitable for entity updates"""
        pass
    
    @classmethod
    def invalid_data(cls) -> Dict[str, Any]:
        """Generate invalid data for negative testing"""
        return {}  # Empty data is universally invalid for creation
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """
        Generate edge case data for boundary testing
        
        Args:
            case_type: Type of edge case ('long_name', 'special_chars', 'unicode', etc.)
            
        Returns:
            Dict containing edge case test data
        """
        if case_type == "empty_strings":
            data = cls.sample_data()
            for key, value in data.items():
                if isinstance(value, str) and value:
                    data[key] = ""
            return data
        
        return cls.sample_data()


@dataclass
class BehaviorDataFactory(BaseDataFactory):
    """Factory for generating behavior test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal behavior data (only required fields)"""
        return {
            "name": fake.catch_phrase()
        }
    
    @classmethod
    def sample_data(cls, name_length: Optional[int] = None, 
                   include_description: bool = True) -> Dict[str, Any]:
        """
        Generate sample behavior data
        
        Args:
            name_length: Override name length (default: random phrase)
            include_description: Whether to include description field
            
        Returns:
            Dict containing behavior data
        """
        if name_length:
            name = fake.text(max_nb_chars=name_length).replace('\n', ' ').strip()
        else:
            name = fake.catch_phrase()
        
        data = {"name": name}
        
        if include_description:
            data["description"] = fake.text(max_nb_chars=200)
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate behavior update data"""
        return {
            "name": fake.sentence(nb_words=3).rstrip('.'),
            "description": fake.paragraph(nb_sentences=2)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate behavior edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=1000).replace('\n', ' '),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"{fake.word()} 🧪 émoji & spëcial chars! @#$%^&*()",
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "unicode":
            return {
                "name": f"Test 测试 тест テスト {fake.word()}",
                "description": "Unicode description: 测试 тест テスト"
            }
        elif case_type == "only_spaces":
            return {
                "name": "   ",
                "description": "     "
            }
        elif case_type == "sql_injection":
            return {
                "name": "'; DROP TABLE behaviors; --",
                "description": "1' OR '1'='1"
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of behavior data
        
        Args:
            count: Number of behavior records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of behavior data dictionaries
        """
        behaviors = []
        for i in range(count):
            if variation:
                # Create varied data
                data = cls.sample_data(
                    include_description=fake.boolean(),
                )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Test Behavior {i+1}",
                    "description": f"Description for test behavior {i+1}"
                }
            behaviors.append(data)
        
        return behaviors


@dataclass 
class TopicDataFactory(BaseDataFactory):
    """Factory for generating topic test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal topic data"""
        return {
            "name": fake.word().title()
        }
    
    @classmethod
    def sample_data(cls, parent_id: Optional[str] = None,
                   include_description: bool = True) -> Dict[str, Any]:
        """
        Generate sample topic data
        
        Args:
            parent_id: Optional parent topic ID for hierarchies
            include_description: Whether to include description
            
        Returns:
            Dict containing topic data
        """
        data = {
            "name": fake.word().title() + " " + fake.word().title()
        }
        
        if include_description:
            data["description"] = fake.text(max_nb_chars=150)
        
        if parent_id:
            data["parent_id"] = parent_id
            
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate topic update data"""
        return {
            "name": fake.bs().title(),
            "description": fake.paragraph(nb_sentences=1)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate topic edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=500).replace('\n', ' '),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"Topic 🏷️ with émoji & chars! {fake.random_element(['@', '#', '$'])}",
                "description": fake.text(max_nb_chars=100)
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def hierarchy_data(cls, depth: int = 2, 
                      children_per_level: int = 2) -> Dict[str, Any]:
        """
        Generate hierarchical topic data structure
        
        Args:
            depth: How deep the hierarchy should go
            children_per_level: Number of children at each level
            
        Returns:
            Dict with parent and nested children structure
        """
        def create_level(level: int, parent_name: str = "") -> Dict[str, Any]:
            if level <= 0:
                return {}
            
            name = f"{parent_name} Level {level}" if parent_name else f"Root Level {level}"
            data = {
                "name": name,
                "description": f"Description for {name}"
            }
            
            if level > 1:
                data["children"] = []
                for i in range(children_per_level):
                    child = create_level(level - 1, f"{name} Child {i+1}")
                    if child:
                        data["children"].append(child)
            
            return data
        
        return create_level(depth)


@dataclass
class CategoryDataFactory(BaseDataFactory):
    """Factory for generating category test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal category data"""
        return {
            "name": fake.word().title() + " Category"
        }
    
    @classmethod
    def sample_data(cls, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate sample category data"""
        data = {
            "name": fake.word().title() + " Category",
            "description": fake.text(max_nb_chars=120)
        }
        
        if parent_id:
            data["parent_id"] = parent_id
            
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate category update data"""
        return {
            "name": fake.company() + " Category",
            "description": fake.paragraph(nb_sentences=1)
        }


@dataclass
class MetricDataFactory(BaseDataFactory):
    """Factory for generating metric test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal metric data (only required fields)"""
        return {
            "name": fake.word().title() + " Metric",
            "evaluation_prompt": fake.sentence(nb_words=8),
            "score_type": fake.random_element(elements=("numeric", "categorical", "binary"))
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample metric data"""
        return {
            "name": fake.word().title() + " " + fake.word().title() + " Metric",
            "description": fake.text(max_nb_chars=150),
            "evaluation_prompt": fake.sentence(nb_words=8),
            "evaluation_steps": fake.text(max_nb_chars=200),
            "reasoning": fake.text(max_nb_chars=100),
            "score_type": fake.random_element(elements=("numeric", "categorical", "binary")),
            "min_score": fake.random_number(digits=1),
            "max_score": fake.random_number(digits=2),
            "reference_score": fake.word(),
            "threshold": fake.random_number(digits=1),
            "threshold_operator": fake.random_element(elements=("=", "<", ">", "<=", ">=", "!=")),
            "explanation": fake.text(max_nb_chars=100),
            "context_required": fake.boolean(),
            "evaluation_examples": fake.text(max_nb_chars=200)
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate metric update data"""
        return {
            "name": fake.bs().title() + " Metric",
            "description": fake.paragraph(nb_sentences=2),
            "evaluation_prompt": fake.sentence(nb_words=10),
            "explanation": fake.text(max_nb_chars=120)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate metric edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=800).replace('\n', ' '),
                "evaluation_prompt": fake.sentence(nb_words=8),
                "score_type": "numeric",
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"{fake.word()} 📊 émoji & metrics! @#$%^&*()",
                "evaluation_prompt": "How well does this handle special chars? 🤔",
                "score_type": "categorical",
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "unicode":
            return {
                "name": f"Test 测试 тест テスト {fake.word()} Metric",
                "evaluation_prompt": "Unicode evaluation: 测试 тест テスト",
                "score_type": "binary",
                "description": "Unicode description: 测试 тест テスト"
            }
        elif case_type == "sql_injection":
            return {
                "name": "'; DROP TABLE metrics; --",
                "evaluation_prompt": "1' OR '1'='1",
                "score_type": "numeric",
                "description": "SQL injection attempt"
            }
        
        return super().edge_case_data(case_type)


@dataclass
class ModelDataFactory(BaseDataFactory):
    """Factory for generating model test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal model data (only required fields)"""
        return {
            "name": fake.company() + " Model",
            "model_name": fake.random_element(elements=("gpt-4", "gpt-3.5-turbo", "claude-3", "gemini-pro")),
            "endpoint": fake.url(),
            "key": fake.uuid4()
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample model data"""
        return {
            "name": fake.company() + " " + fake.word().title() + " Model",
            "description": fake.text(max_nb_chars=150),
            "icon": fake.random_element(elements=("🤖", "⚡", "🧠", "🔮")),
            "model_name": fake.random_element(elements=("gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "gemini-pro", "llama-2")),
            "endpoint": fake.url() + "/v1/chat/completions",
            "key": fake.uuid4(),
            "request_headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {fake.uuid4()}"
            }
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate model update data"""
        return {
            "name": fake.company() + " Updated Model",
            "description": fake.paragraph(nb_sentences=2),
            "endpoint": fake.url() + "/api/v2",
            "key": fake.uuid4()
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate model edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=800).replace('\n', ' '),
                "model_name": "very-long-model-name-that-might-cause-issues",
                "endpoint": fake.url(),
                "key": fake.uuid4(),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"{fake.word()} 🤖 émoji & AI model! @#$%^&*()",
                "model_name": "special-char-model-🤖",
                "endpoint": fake.url(),
                "key": fake.uuid4(),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "unicode":
            return {
                "name": f"Test 测试 тест テスト {fake.word()} Model",
                "model_name": "unicode-model-测试",
                "endpoint": fake.url(),
                "key": fake.uuid4(),
                "description": "Unicode description: 测试 тест テスト"
            }
        elif case_type == "sql_injection":
            return {
                "name": "'; DROP TABLE models; --",
                "model_name": "1' OR '1'='1",
                "endpoint": fake.url(),
                "key": fake.uuid4(),
                "description": "SQL injection attempt"
            }
        
        return super().edge_case_data(case_type)


@dataclass
class OrganizationDataFactory(BaseDataFactory):
    """Factory for generating organization test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal organization data (only required fields)"""
        # Generate a placeholder UUID for user relationships
        # Tests with access to authenticated_user should override these
        placeholder_user_id = str(fake.uuid4())
        
        return {
            "name": fake.company(),
            # Required user relationships - tests should override with real user IDs
            "owner_id": placeholder_user_id,
            "user_id": placeholder_user_id
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample organization data"""
        # Generate a placeholder UUID for user relationships
        # Tests with access to authenticated_user should override these
        placeholder_user_id = str(fake.uuid4())
        
        return {
            "name": fake.company(),
            "display_name": fake.company() + " Corp",
            "description": fake.text(max_nb_chars=200),
            "website": fake.url(),
            "logo_url": fake.image_url(),
            "email": fake.company_email(),
            "phone": fake.phone_number(),
            "address": fake.address().replace('\n', ', '),
            "is_active": fake.boolean(chance_of_getting_true=85),
            "max_users": fake.random_int(min=5, max=100),
            "domain": fake.domain_name(),
            "is_domain_verified": fake.boolean(chance_of_getting_true=30),
            "is_onboarding_complete": fake.boolean(chance_of_getting_true=70),
            # Required user relationships - tests should override with real user IDs
            "owner_id": placeholder_user_id,
            "user_id": placeholder_user_id
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate organization update data"""
        return {
            "name": fake.company() + " Updated",  # Optional for updates, but good to test
            "display_name": fake.company() + " Updated Corp",
            "description": fake.paragraph(nb_sentences=2),
            "website": fake.url(),
            "email": fake.company_email(),
            "phone": fake.phone_number(),
            "is_active": fake.boolean(chance_of_getting_true=90)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate organization edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=800).replace('\n', ' '),
                "description": fake.text(max_nb_chars=100),
                "email": fake.company_email()
            }
        elif case_type == "special_chars":
            return {
                "name": f"{fake.company()} 🏢 émoji & company! @#$%^&*()",
                "display_name": f"Special Chars Corp 🏢",
                "description": fake.text(max_nb_chars=100),
                "email": fake.company_email()
            }
        elif case_type == "unicode":
            return {
                "name": f"Test 测试 тест テスト {fake.company()}",
                "display_name": "Unicode Corp 测试",
                "description": "Unicode description: 测试 тест テスト",
                "email": fake.company_email()
            }
        elif case_type == "sql_injection":
            return {
                "name": "'; DROP TABLE organization; --",
                "display_name": "1' OR '1'='1",
                "description": "SQL injection attempt",
                "email": fake.company_email()
            }
        elif case_type == "max_limits":
            return {
                "name": fake.company(),
                "max_users": 1000,
                "description": fake.text(max_nb_chars=2000),
                "address": fake.text(max_nb_chars=1000)
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def onboarding_incomplete_data(cls) -> Dict[str, Any]:
        """Generate organization data for onboarding tests"""
        data = cls.sample_data()
        data["is_onboarding_complete"] = False
        return data
    
    @classmethod
    def onboarding_complete_data(cls) -> Dict[str, Any]:
        """Generate organization data with completed onboarding"""
        data = cls.sample_data()
        data["is_onboarding_complete"] = True
        return data


@dataclass
class DimensionDataFactory(BaseDataFactory):
    """Factory for generating dimension test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal dimension data"""
        return {
            "name": fake.word().title() + " Dimension"
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample dimension data"""
        return {
            "name": fake.word().title() + " Dimension",
            "description": fake.text(max_nb_chars=180)
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate dimension update data"""
        return {
            "name": fake.catch_phrase() + " Dimension",
            "description": fake.paragraph(nb_sentences=1)
        }


@dataclass
class ProjectDataFactory(BaseDataFactory):
    """Factory for generating project test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal project data (only required fields)"""
        return {
            "name": fake.catch_phrase() + " Project"
        }
    
    @classmethod
    def sample_data(cls, include_description: bool = True) -> Dict[str, Any]:
        """
        Generate sample project data (following working behavior pattern)
        
        Args:
            include_description: Whether to include description field
            
        Returns:
            Dict containing project test data
        """
        data = {
            "name": fake.company() + " " + fake.bs().title() + " Project"
        }
        
        if include_description:
            data["description"] = fake.text(max_nb_chars=200)
            
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate project update data"""
        return {
            "name": fake.catch_phrase() + " Updated Project",
            "description": fake.paragraph(nb_sentences=2),
            "icon": "🔄"
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate edge case project data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=500).replace('\n', ' ') + " Project",
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"🚀 {fake.company()} with émoji & spëcial chars! Project {fake.random_element(elements=['@', '#', '$', '%'])}",
                "description": fake.text(max_nb_chars=150)
            }
        elif case_type == "inactive":
            return {
                "name": fake.company() + " Inactive Project",
                "description": fake.text(max_nb_chars=100)
            }
        
        return cls.sample_data()


@dataclass
class PromptDataFactory(BaseDataFactory):
    """Factory for generating prompt test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal prompt data (only required fields)"""
        return {
            "content": fake.sentence(nb_words=8),
            "language_code": "en"
        }
    
    @classmethod
    def sample_data(cls, include_expected_response: bool = True,
                   include_relationships: bool = True,
                   language_code: str = "en") -> Dict[str, Any]:
        """
        Generate sample prompt data
        
        Args:
            include_expected_response: Whether to include expected response
            include_relationships: Whether to include relationship fields
            language_code: Language code for the prompt
            
        Returns:
            Dict containing prompt test data
        """
        data = {
            "content": fake.paragraph(nb_sentences=3),
            "language_code": language_code
        }
        
        if include_expected_response:
            data["expected_response"] = fake.paragraph(nb_sentences=2)
        
        # Note: Relationship fields (demographic_id, category_id, etc.) 
        # are typically set by fixtures or test setup, not in sample data
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate prompt update data"""
        return {
            "content": fake.paragraph(nb_sentences=4),
            "expected_response": fake.paragraph(nb_sentences=3),
            "language_code": fake.random_element(elements=["en", "es", "fr", "de"])
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate edge case prompt data"""
        if case_type == "long_content":
            return {
                "content": fake.text(max_nb_chars=2000),
                "language_code": "en",
                "expected_response": fake.text(max_nb_chars=1000)
            }
        elif case_type == "special_chars":
            return {
                "content": f"🤖 {fake.sentence()} with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}",
                "language_code": "en"
            }
        elif case_type == "multilingual":
            return {
                "content": "¿Cómo estás? Comment allez-vous? Wie geht es dir?",
                "language_code": "es",
                "expected_response": "I am doing well, thank you!"
            }
        elif case_type == "multiturn":
            return {
                "content": fake.sentence(nb_words=10),
                "language_code": "en",
                # parent_id would be set by the test when creating child prompts
            }
        
        return cls.sample_data()
    
    @classmethod
    def conversation_data(cls, turn_number: int = 1) -> Dict[str, Any]:
        """Generate conversation turn data for multiturn scenarios"""
        return {
            "content": f"Turn {turn_number}: {fake.sentence(nb_words=8)}",
            "language_code": "en",
            "expected_response": f"Response to turn {turn_number}: {fake.sentence(nb_words=6)}"
        }


# Factory registry for dynamic access
FACTORY_REGISTRY = {
    "behavior": BehaviorDataFactory,
    "topic": TopicDataFactory,
    "category": CategoryDataFactory,
    "metric": MetricDataFactory,
    "model": ModelDataFactory,
    "organization": OrganizationDataFactory,
    "dimension": DimensionDataFactory,
    "project": ProjectDataFactory,
    "prompt": PromptDataFactory,
}


def get_factory(entity_type: str) -> BaseDataFactory:
    """
    Get data factory for entity type
    
    Args:
        entity_type: Type of entity ('behavior', 'topic', etc.)
        
    Returns:
        Data factory class for the entity
        
    Raises:
        KeyError: If entity type not found
    """
    if entity_type not in FACTORY_REGISTRY:
        raise KeyError(f"No factory found for entity type: {entity_type}")
    
    return FACTORY_REGISTRY[entity_type]


def generate_test_data(entity_type: str, data_type: str = "sample", 
                      **kwargs) -> Dict[str, Any]:
    """
    Generate test data for any entity type
    
    Args:
        entity_type: Type of entity ('behavior', 'topic', etc.)
        data_type: Type of data ('minimal', 'sample', 'update', 'edge_case')
        **kwargs: Additional arguments passed to factory method
        
    Returns:
        Generated test data
    """
    factory = get_factory(entity_type)
    
    if data_type == "minimal":
        return factory.minimal_data()
    elif data_type == "sample":
        return factory.sample_data(**kwargs)
    elif data_type == "update":
        return factory.update_data()
    elif data_type == "edge_case":
        case_type = kwargs.get("case_type", "long_name")
        return factory.edge_case_data(case_type)
    else:
        raise ValueError(f"Unknown data type: {data_type}")


# Export main classes and functions
__all__ = [
    "BaseDataFactory",
    "BehaviorDataFactory",
    "TopicDataFactory", 
    "CategoryDataFactory",
    "MetricDataFactory",
    "ModelDataFactory",
    "OrganizationDataFactory",
    "DimensionDataFactory",
    "FACTORY_REGISTRY",
    "get_factory",
    "generate_test_data"
]

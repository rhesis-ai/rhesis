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

from rhesis.backend.app.constants import EntityType

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
        import time
        unique_suffix = f"{int(time.time() * 1000000) % 1000000}"  # microsecond timestamp
        return {
            "name": f"{fake.catch_phrase()} Project {unique_suffix}"
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
        import time
        unique_suffix = f"{int(time.time() * 1000000) % 1000000}"  # microsecond timestamp
        data = {
            "name": f"{fake.company()} {fake.bs().title()} Project {unique_suffix}"
        }
        
        if include_description:
            data["description"] = fake.text(max_nb_chars=200)
            
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate project update data"""
        import time
        unique_suffix = f"{int(time.time() * 1000000) % 1000000}"  # microsecond timestamp
        return {
            "name": f"{fake.catch_phrase()} Updated Project {unique_suffix}",
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


class EndpointDataFactory(BaseDataFactory):
    """
    Endpoint Data Factory for generating endpoint entity data
    
    Provides consistent endpoint data generation for Endpoint entities with various
    scenarios including minimal data, comprehensive data, and edge cases.
    """
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal required data for Endpoint entity creation"""
        return {
            "name": fake.word().title() + " Endpoint",
            "protocol": "REST",
            "url": fake.url(),
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate comprehensive sample data for Endpoint entity"""
        return {
            **cls.minimal_data(),
            "description": fake.sentence(),
            "environment": fake.random_element(elements=("development", "staging", "production")),
            "config_source": fake.random_element(elements=("manual", "openapi", "llm_generated")),
            "method": fake.random_element(elements=("GET", "POST", "PUT", "DELETE", "PATCH")),
            "endpoint_path": f"/{fake.word()}/{fake.word()}",
            "request_headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer {token}"
            },
            "query_params": {
                "limit": 10,
                "offset": 0
            },
            "request_body_template": {
                "name": "{name}",
                "value": "{value}"
            },
            "response_format": fake.random_element(elements=("json", "xml", "text")),
            "response_mappings": {
                "data": "$.result",
                "error": "$.error"
            },
            "validation_rules": {
                "status_code": [200, 201],
                "response_time": {"max": 5000}
            },
            "auth_type": fake.random_element(elements=("bearer", "api_key", "oauth2")),
            "auth": {
                "type": "bearer",
                "token": fake.sha256()
            }
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate data for updating Endpoint entities"""
        return {
            "description": fake.sentence(),
            "environment": fake.random_element(elements=("development", "staging", "production")),
            "auth": {
                "type": "api_key",
                "key": fake.sha256()
            }
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate edge case data for Endpoint entities"""
        base_data = cls.sample_data()
        
        if case_type == "minimal":
            return cls.minimal_data()
        elif case_type == "websocket":
            base_data.update({
                "protocol": "WebSocket",
                "url": f"wss://{fake.domain_name()}/ws",
                "method": None,
                "endpoint_path": None
            })
        elif case_type == "grpc":
            base_data.update({
                "protocol": "GRPC",
                "url": f"grpc://{fake.domain_name()}:9090",
                "method": None,
                "endpoint_path": f"{fake.word()}.{fake.word()}"
            })
        elif case_type == "oauth2":
            base_data.update({
                "auth_type": "oauth2",
                "client_id": fake.uuid4(),
                "client_secret": fake.sha256(),
                "token_url": fake.url() + "/oauth/token",
                "scopes": ["read", "write"],
                "audience": fake.domain_name()
            })
        elif case_type == "complex_config":
            base_data.update({
                "openapi_spec": {
                    "openapi": "3.0.0",
                    "info": {"title": fake.sentence(), "version": "1.0.0"},
                    "paths": {
                        "/test": {
                            "get": {
                                "responses": {"200": {"description": "Success"}}
                            }
                        }
                    }
                },
                "llm_suggestions": {
                    "confidence": 0.95,
                    "suggested_params": ["id", "name", "status"]
                }
            })
        
        return base_data


# Factory registry for dynamic access - moved after all factory definitions
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
    "endpoint": EndpointDataFactory,
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


@dataclass
class PromptTemplateDataFactory(BaseDataFactory):
    """Factory for generating prompt template test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal prompt template data (only required fields)"""
        return {
            "content": fake.text(max_nb_chars=100),
            "language_code": "en"
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample prompt template data"""
        data = {
            "content": fake.text(max_nb_chars=200),
            "language_code": fake.random_element(elements=("en", "es", "fr", "de", "zh"))
        }
        
        if include_optional:
            data.update({
                "is_summary": fake.boolean(),
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate prompt template update data"""
        return {
            "content": fake.text(max_nb_chars=150),
            "language_code": fake.random_element(elements=("en", "es", "fr"))
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate prompt template edge case data"""
        if case_type == "long_content":
            return {
                "content": fake.text(max_nb_chars=5000),
                "language_code": "en"
            }
        elif case_type == "special_chars":
            return {
                "content": f"Template with émojis 🤖 and spëcial chars! @#$%^&*()",
                "language_code": "en"
            }
        elif case_type == "unicode":
            return {
                "content": f"Template 测试 тест テスト {fake.text(max_nb_chars=50)}",
                "language_code": "zh"
            }
        
        return super().edge_case_data(case_type)


@dataclass
class ResponsePatternDataFactory(BaseDataFactory):
    """Factory for generating response pattern test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal response pattern data (only required fields)"""
        return {
            "text": fake.text(max_nb_chars=100),
            "behavior_id": fake.uuid4()
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample response pattern data"""
        data = {
            "text": fake.text(max_nb_chars=200),
            "behavior_id": fake.uuid4()
        }
        
        # Note: response_pattern_type_id is optional but requires a valid foreign key
        # For now, we'll omit it to avoid foreign key constraints in tests
        # Individual tests can add it if they create the necessary type_lookup entries
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate response pattern update data"""
        return {
            "text": fake.text(max_nb_chars=150),
            "behavior_id": fake.uuid4()
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate response pattern edge case data"""
        if case_type == "long_text":
            return {
                "text": fake.text(max_nb_chars=5000),
                "behavior_id": fake.uuid4()
            }
        elif case_type == "special_chars":
            return {
                "text": f"Response with émojis 🤖 and spëcial chars! @#$%^&*()",
                "behavior_id": fake.uuid4()
            }
        
        return super().edge_case_data(case_type)


@dataclass
class SourceDataFactory(BaseDataFactory):
    """Factory for generating source test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal source data (only required fields)"""
        return {
            "title": fake.sentence(nb_words=3).rstrip('.')
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample source data"""
        data = {
            "title": fake.sentence(nb_words=4).rstrip('.')
        }
        
        if include_optional:
            data.update({
                "description": fake.text(max_nb_chars=300),
                # source_type_id is optional and requires a valid type_lookup record
                # "source_type_id": str(fake.uuid4()),  # UUID for type_lookup reference
                "url": fake.url(),  # Faker returns string, which is what we want
                "citation": f"{fake.name()} et al. ({fake.year()}). {fake.sentence()}",
                "language_code": fake.random_element(elements=("en", "es", "fr", "de", "zh"))
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate source update data"""
        return {
            "title": fake.sentence(nb_words=3).rstrip('.'),
            "description": fake.text(max_nb_chars=200),
            "entity_type": fake.random_element(elements=("website", "paper", "book"))
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate source edge case data"""
        if case_type == "long_title":
            return {
                "title": fake.text(max_nb_chars=500).replace('\n', ' '),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "title": f"Source with émojis 📚 and spëcial chars! @#$%^&*()",
                "description": fake.text(max_nb_chars=100)
            }
        
        return super().edge_case_data(case_type)


@dataclass
class StatusDataFactory(BaseDataFactory):
    """Factory for generating status test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal status data (only required fields)"""
        return {
            "name": fake.word().title()
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample status data"""
        data = {
            "name": fake.word().title()
        }
        
        if include_optional:
            data.update({
                "description": fake.text(max_nb_chars=200)
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate status update data"""
        return {
            "name": fake.word().title(),
            "description": fake.text(max_nb_chars=150)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate status edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=200).replace('\n', ' '),
                "description": fake.text(max_nb_chars=100)
            }
        elif case_type == "special_chars":
            return {
                "name": f"Status with émojis ⚡ and spëcial chars! @#$%^&*()",
                "description": fake.text(max_nb_chars=100)
            }
        
        return super().edge_case_data(case_type)


@dataclass
class RiskDataFactory(BaseDataFactory):
    """Factory for generating risk test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal risk data (only required fields)"""
        return {
            "name": f"Risk: {fake.catch_phrase()}"
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample risk data"""
        data = {
            "name": f"Risk: {fake.catch_phrase()}"
        }
        
        if include_optional:
            data.update({
                "description": fake.paragraph(nb_sentences=3),
                # Foreign key relationships will be handled by fixtures
                # parent_id: Optional - self-referential for hierarchical risks
                # use_case_id: Optional - reference to use case
                # status_id: Optional - reference to status
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate risk update data"""
        return {
            "name": f"Updated Risk: {fake.catch_phrase()}",
            "description": fake.paragraph(nb_sentences=2),
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate risk edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=200).replace('\n', ' '),
                "description": fake.paragraph(nb_sentences=5)
            }
        elif case_type == "security_risk":
            security_risks = [
                "Risk: Data breach vulnerability in authentication system",
                "Risk: SQL injection vulnerability in user input validation",
                "Risk: Cross-site scripting (XSS) vulnerability in web forms",
                "Risk: Unauthorized access to sensitive customer data",
                "Risk: Insufficient encryption of data in transit"
            ]
            return {
                "name": fake.random_element(elements=security_risks),
                "description": fake.paragraph(nb_sentences=4)
            }
        elif case_type == "operational_risk":
            operational_risks = [
                "Risk: System downtime during peak business hours",
                "Risk: Database corruption due to hardware failure",
                "Risk: Third-party service dependency failure",
                "Risk: Insufficient backup and disaster recovery procedures",
                "Risk: Staff unavailability during critical operations"
            ]
            return {
                "name": fake.random_element(elements=operational_risks),
                "description": fake.paragraph(nb_sentences=3)
            }
        elif case_type == "compliance_risk":
            compliance_risks = [
                "Risk: Non-compliance with GDPR data protection requirements",
                "Risk: Failure to meet industry regulatory standards",
                "Risk: Inadequate audit trail for financial transactions",
                "Risk: Missing documentation for compliance reporting",
                "Risk: Insufficient data retention policy implementation"
            ]
            return {
                "name": fake.random_element(elements=compliance_risks),
                "description": fake.paragraph(nb_sentences=4)
            }
        elif case_type == "financial_risk":
            financial_risks = [
                "Risk: Budget overrun due to scope creep",
                "Risk: Revenue loss from service interruptions",
                "Risk: Cost escalation in third-party services",
                "Risk: Currency exchange rate fluctuations",
                "Risk: Unexpected infrastructure scaling costs"
            ]
            return {
                "name": fake.random_element(elements=financial_risks),
                "description": fake.paragraph(nb_sentences=3)
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of risk data
        
        Args:
            count: Number of risk records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of risk data dictionaries
        """
        risks = []
        risk_categories = ["security_risk", "operational_risk", "compliance_risk", "financial_risk"]
        
        for i in range(count):
            if variation:
                # Create varied data using different risk categories
                if i < len(risk_categories):
                    data = cls.edge_case_data(risk_categories[i])
                else:
                    data = cls.sample_data(
                        include_optional=fake.boolean(),
                    )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Risk {i+1}: {fake.catch_phrase()}",
                    "description": fake.paragraph(nb_sentences=2)
                }
            risks.append(data)
        
        return risks


@dataclass
class UseCaseDataFactory(BaseDataFactory):
    """Factory for generating use case test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal use case data (only required fields)"""
        return {
            "name": f"Use Case: {fake.catch_phrase()}",
            "description": fake.paragraph(nb_sentences=2)
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample use case data"""
        data = {
            "name": f"Use Case: {fake.catch_phrase()}",
            "description": fake.paragraph(nb_sentences=3)
        }
        
        if include_optional:
            industries = [
                "Healthcare", "Finance", "E-commerce", "Education", "Manufacturing",
                "Technology", "Retail", "Automotive", "Media", "Real Estate",
                "Insurance", "Telecommunications", "Energy", "Transportation"
            ]
            
            applications = [
                "Customer Support", "Data Analysis", "Content Generation", "Process Automation",
                "Quality Assurance", "Risk Assessment", "Fraud Detection", "Personalization",
                "Recommendation Systems", "Document Processing", "Image Recognition",
                "Natural Language Processing", "Predictive Analytics", "Workflow Optimization"
            ]
            
            data.update({
                "industry": fake.random_element(elements=industries),
                "application": fake.random_element(elements=applications),
                "is_active": fake.boolean(chance_of_getting_true=80),  # Most use cases are active
                # Foreign key relationships will be handled by fixtures
                # status_id: Optional - reference to status
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate use case update data"""
        industries = ["Technology", "Healthcare", "Finance", "E-commerce", "Education"]
        applications = ["AI/ML", "Automation", "Analytics", "Customer Service", "Quality Control"]
        
        return {
            "name": f"Updated Use Case: {fake.catch_phrase()}",
            "description": fake.paragraph(nb_sentences=2),
            "industry": fake.random_element(elements=industries),
            "application": fake.random_element(elements=applications),
            "is_active": fake.boolean(chance_of_getting_true=75)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate use case edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=200).replace('\n', ' '),
                "description": fake.paragraph(nb_sentences=5),
                "industry": "Technology",
                "application": "Complex System Integration"
            }
        elif case_type == "healthcare":
            healthcare_use_cases = [
                "Use Case: Patient Data Analysis for Personalized Treatment Plans",
                "Use Case: Medical Image Analysis for Early Disease Detection",
                "Use Case: Drug Discovery and Development Acceleration",
                "Use Case: Electronic Health Record Management and Analytics",
                "Use Case: Telemedicine Platform with AI-Powered Diagnosis"
            ]
            return {
                "name": fake.random_element(elements=healthcare_use_cases),
                "description": fake.paragraph(nb_sentences=4),
                "industry": "Healthcare",
                "application": fake.random_element(elements=[
                    "Clinical Decision Support", "Medical Imaging", "Drug Discovery",
                    "Electronic Health Records", "Telemedicine"
                ]),
                "is_active": True
            }
        elif case_type == "finance":
            finance_use_cases = [
                "Use Case: Automated Fraud Detection and Prevention System",
                "Use Case: Algorithmic Trading Strategy Optimization",
                "Use Case: Credit Risk Assessment and Loan Approval Automation",
                "Use Case: Regulatory Compliance Monitoring and Reporting",
                "Use Case: Customer Portfolio Management and Investment Advisory"
            ]
            return {
                "name": fake.random_element(elements=finance_use_cases),
                "description": fake.paragraph(nb_sentences=4),
                "industry": "Finance",
                "application": fake.random_element(elements=[
                    "Fraud Detection", "Algorithmic Trading", "Risk Assessment",
                    "Compliance", "Portfolio Management"
                ]),
                "is_active": True
            }
        elif case_type == "ecommerce":
            ecommerce_use_cases = [
                "Use Case: Personalized Product Recommendation Engine",
                "Use Case: Dynamic Pricing Optimization Based on Market Conditions",
                "Use Case: Customer Behavior Analysis for Marketing Campaigns",
                "Use Case: Inventory Management and Demand Forecasting",
                "Use Case: Chatbot Customer Service and Support Automation"
            ]
            return {
                "name": fake.random_element(elements=ecommerce_use_cases),
                "description": fake.paragraph(nb_sentences=3),
                "industry": "E-commerce",
                "application": fake.random_element(elements=[
                    "Recommendation Systems", "Dynamic Pricing", "Customer Analytics",
                    "Inventory Management", "Customer Support"
                ]),
                "is_active": True
            }
        elif case_type == "inactive":
            return {
                "name": f"Use Case: Deprecated - {fake.catch_phrase()}",
                "description": f"This use case has been deprecated. {fake.paragraph(nb_sentences=2)}",
                "industry": fake.random_element(elements=["Legacy Systems", "Outdated Technology"]),
                "application": "Discontinued Service",
                "is_active": False
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of use case data
        
        Args:
            count: Number of use case records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of use case data dictionaries
        """
        use_cases = []
        categories = ["healthcare", "finance", "ecommerce", "inactive"]
        
        for i in range(count):
            if variation:
                # Create varied data using different categories
                if i < len(categories):
                    data = cls.edge_case_data(categories[i])
                else:
                    data = cls.sample_data(
                        include_optional=fake.boolean(chance_of_getting_true=80),
                    )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Use Case {i+1}: {fake.catch_phrase()}",
                    "description": fake.paragraph(nb_sentences=2),
                    "industry": "Technology",
                    "application": "General Purpose",
                    "is_active": True
                }
            use_cases.append(data)
        
        return use_cases


@dataclass
class TopicDataFactory(BaseDataFactory):
    """Factory for generating topic test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal topic data (only required fields)"""
        return {
            "name": f"Topic: {fake.catch_phrase()}"
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample topic data"""
        data = {
            "name": f"Topic: {fake.catch_phrase()}"
        }
        
        if include_optional:
            data.update({
                "description": fake.paragraph(nb_sentences=2),
                # Foreign key relationships will be handled by fixtures
                # parent_id: Optional - self-referential for hierarchical structure
                # entity_type_id: Optional - reference to entity type
                # status_id: Optional - reference to status
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate topic update data"""
        return {
            "name": f"Updated Topic: {fake.catch_phrase()}",
            "description": fake.paragraph(nb_sentences=1)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate topic edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=200).replace('\n', ' '),
                "description": fake.paragraph(nb_sentences=3)
            }
        elif case_type == "hierarchical_topics":
            # Topics for hierarchical testing
            topic_categories = [
                "Technology: Artificial Intelligence and Machine Learning",
                "Business: Strategic Planning and Operations", 
                "Science: Research Methodology and Analysis",
                "Education: Curriculum Development and Assessment",
                "Healthcare: Patient Care and Medical Innovation"
            ]
            return {
                "name": fake.random_element(elements=topic_categories),
                "description": fake.paragraph(nb_sentences=2)
            }
        elif case_type == "specialized_domains":
            # Domain-specific topics
            domains = {
                "AI/ML": ["Deep Learning", "Neural Networks", "Computer Vision", "Natural Language Processing"],
                "Business": ["Market Analysis", "Financial Planning", "Risk Management", "Customer Experience"],
                "Science": ["Data Analysis", "Research Design", "Statistical Methods", "Experimental Design"],
                "Technology": ["Software Architecture", "Cloud Computing", "DevOps", "Cybersecurity"],
                "Healthcare": ["Clinical Trials", "Patient Safety", "Medical Devices", "Telemedicine"]
            }
            domain = fake.random_element(elements=list(domains.keys()))
            topic = fake.random_element(elements=domains[domain])
            return {
                "name": f"Topic: {domain} - {topic}",
                "description": f"Comprehensive coverage of {topic.lower()} within the {domain.lower()} domain. {fake.paragraph(nb_sentences=1)}"
            }
        elif case_type == "empty_description":
            return {
                "name": f"Topic: {fake.catch_phrase()}",
                "description": ""
            }
        elif case_type == "null_description":
            return {
                "name": f"Topic: {fake.catch_phrase()}",
                "description": None
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of topic data
        
        Args:
            count: Number of topic records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of topic data dictionaries
        """
        topics = []
        categories = ["hierarchical_topics", "specialized_domains"]
        
        for i in range(count):
            if variation:
                # Create varied data using different categories
                if i < len(categories):
                    data = cls.edge_case_data(categories[i % len(categories)])
                else:
                    data = cls.sample_data(
                        include_optional=fake.boolean(chance_of_getting_true=80),
                    )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Topic {i+1}: {fake.catch_phrase()}",
                    "description": fake.paragraph(nb_sentences=1)
                }
            topics.append(data)
        
        return topics


@dataclass
class TokenDataFactory(BaseDataFactory):
    """Factory for generating token test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal token data (only required fields) - API format"""
        return {
            "name": f"Test Token {fake.word()}"
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample token data - API format"""
        data = {
            "name": f"Test Token {fake.word()}"
        }
        
        if include_optional:
            # Add expiration in days (API format)
            data.update({
                "expires_in_days": 30
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate token update data"""
        token_value = cls._generate_test_token()
        from datetime import datetime, timezone
        return {
            "name": f"Updated Token {fake.word()}",
            "token": token_value,
            "token_obfuscated": cls._obfuscate_token(token_value),
            "last_refreshed_at": datetime.now(timezone.utc)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate token edge case data - API format"""
        
        if case_type == "expired_token":
            return {
                "name": f"Expired Token {fake.word()}",
                "expires_in_days": -1  # Expired (will be handled by API)
            }
        elif case_type == "long_lived_token":
            return {
                "name": f"Long-lived Token {fake.word()}",
                "expires_in_days": 365  # 1 year
            }
        elif case_type == "never_expires":
            return {
                "name": f"Never Expires Token {fake.word()}"
                # No expires_in_days means it never expires
            }
        elif case_type == "api_integration":
            return {
                "name": f"API Integration - {fake.company()}",
                "expires_in_days": 90
            }
        elif case_type == "development_token":
            return {
                "name": f"Development Token - {fake.user_name()}",
                "expires_in_days": 7  # Short-lived for dev
            }
        elif case_type == "production_token":
            return {
                "name": f"Production Token - {fake.catch_phrase()}",
                "expires_in_days": 180  # 6 months
            }
        elif case_type == "recently_used":
            return {
                "name": f"Recently Used Token {fake.word()}",
                "expires_in_days": 30
            }
        elif case_type == "recently_refreshed":
            return {
                "name": f"Recently Refreshed Token {fake.word()}",
                "expires_in_days": 30
            }
        elif case_type == "long_token_name":
            # Ensure the name is actually longer than 100 characters
            long_name = fake.text(max_nb_chars=200).replace('\n', ' ')
            while len(long_name) <= 100:
                long_name += f" {fake.sentence(nb_words=10).replace('.', '')}"
            return {
                "name": long_name[:150],  # Cap at 150 to avoid excessive length
                "expires_in_days": 30
            }
        elif case_type == "special_chars_name":
            return {
                "name": f"Token with Special Chars @#$%^&*()_+ {fake.word()}",
                "expires_in_days": 30
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of token data - API format
        
        Args:
            count: Number of token records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of token data dictionaries
        """
        tokens = []
        categories = ["api_integration", "development_token", "production_token", "long_lived_token"]
        
        for i in range(count):
            if variation:
                # Create varied data using different categories
                if i < len(categories):
                    data = cls.edge_case_data(categories[i % len(categories)])
                else:
                    data = cls.sample_data(
                        include_optional=fake.boolean(chance_of_getting_true=80),
                    )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Batch Token {i+1}",
                    "expires_in_days": 30
                }
            tokens.append(data)
        
        return tokens
    
    @classmethod
    def _generate_test_token(cls) -> str:
        """Generate a test token value"""
        import secrets
        import string
        
        # Generate a secure random token for testing
        # Use rhesis prefix to identify test tokens
        alphabet = string.ascii_letters + string.digits
        token_suffix = ''.join(secrets.choice(alphabet) for _ in range(32))
        return f"rh-test_{token_suffix}"
    
    @classmethod
    def _obfuscate_token(cls, token: str) -> str:
        """Create an obfuscated version of the token"""
        if len(token) < 8:
            return token  # Too short to obfuscate safely
        return f"{token[:3]}...{token[-4:]}"


@dataclass
class TypeLookupDataFactory(BaseDataFactory):
    """Factory for generating type lookup test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal type lookup data (only required fields)"""
        return {
            "type_name": f"test_type_{fake.word()}",
            "type_value": f"test_value_{fake.word()}"
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample type lookup data"""
        data = {
            "type_name": f"test_type_{fake.word()}",
            "type_value": f"test_value_{fake.word()}"
        }
        
        if include_optional:
            data.update({
                "description": fake.sentence(nb_words=6)
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate type lookup update data"""
        return {
            "type_name": f"updated_type_{fake.word()}",
            "type_value": f"updated_value_{fake.word()}",
            "description": fake.sentence(nb_words=4)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate type lookup edge case data"""
        if case_type == "priority_levels":
            priority_types = [
                ("priority", "low", "Low priority items"),
                ("priority", "medium", "Medium priority items"),
                ("priority", "high", "High priority items"),
                ("priority", "critical", "Critical priority items"),
                ("priority", "urgent", "Urgent priority items")
            ]
            type_name, type_value, description = fake.random_element(elements=priority_types)
            return {
                "type_name": type_name,
                "type_value": type_value,
                "description": description
            }
        elif case_type == "status_types":
            status_types = [
                ("status", "active", "Active status"),
                ("status", "inactive", "Inactive status"),
                ("status", "pending", "Pending status"),
                ("status", "completed", "Completed status"),
                ("status", "cancelled", "Cancelled status"),
                ("status", "draft", "Draft status"),
                ("status", "published", "Published status")
            ]
            type_name, type_value, description = fake.random_element(elements=status_types)
            return {
                "type_name": type_name,
                "type_value": type_value,
                "description": description
            }
        elif case_type == "category_types":
            category_types = [
                ("category", "business", "Business category"),
                ("category", "technology", "Technology category"),
                ("category", "finance", "Finance category"),
                ("category", "healthcare", "Healthcare category"),
                ("category", "education", "Education category"),
                ("category", "research", "Research category"),
                ("category", "marketing", "Marketing category")
            ]
            type_name, type_value, description = fake.random_element(elements=category_types)
            return {
                "type_name": type_name,
                "type_value": type_value,
                "description": description
            }
        elif case_type == "entity_types":
            entity_types = [
                ("entity_type", "user", "User entity type"),
                ("entity_type", "organization", "Organization entity type"),
                ("entity_type", "project", "Project entity type"),
                ("entity_type", "task", "Task entity type"),
                ("entity_type", "document", "Document entity type"),
                ("entity_type", "report", "Report entity type"),
                ("entity_type", "metric", "Metric entity type")
            ]
            type_name, type_value, description = fake.random_element(elements=entity_types)
            return {
                "type_name": type_name,
                "type_value": type_value,
                "description": description
            }
        elif case_type == "long_values":
            return {
                "type_name": f"long_type_{fake.word()}",
                "type_value": fake.text(max_nb_chars=200).replace('\n', ' '),
                "description": fake.paragraph(nb_sentences=3)
            }
        elif case_type == "special_characters":
            return {
                "type_name": f"special_type_{fake.word()}",
                "type_value": "value_with_special_chars_@#$%^&*()_+[]|\\:;\"'<>?,./",
                "description": "Type lookup with special characters in value"
            }
        elif case_type == "null_description":
            return {
                "type_name": f"no_desc_type_{fake.word()}",
                "type_value": f"no_desc_value_{fake.word()}",
                "description": None
            }
        elif case_type == "empty_description":
            return {
                "type_name": f"empty_desc_type_{fake.word()}",
                "type_value": f"empty_desc_value_{fake.word()}",
                "description": ""
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of type lookup data
        
        Args:
            count: Number of type lookup records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of type lookup data dictionaries
        """
        type_lookups = []
        categories = ["priority_levels", "status_types", "category_types", "entity_types"]
        
        for i in range(count):
            if variation:
                # Create varied data using different categories
                if i < len(categories):
                    data = cls.edge_case_data(categories[i % len(categories)])
                else:
                    data = cls.sample_data(
                        include_optional=fake.boolean(chance_of_getting_true=80),
                    )
            else:
                # Create similar data with incremental names
                data = {
                    "type_name": f"batch_type_{i+1}",
                    "type_value": f"batch_value_{i+1}",
                    "description": f"Batch generated type lookup {i+1}"
                }
            type_lookups.append(data)
        
        return type_lookups


@dataclass
class CommentDataFactory(BaseDataFactory):
    """Factory for generating comment test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal comment data (only required fields)"""
        return {
            "content": fake.sentence(nb_words=8),
            "entity_id": fake.uuid4(),  # Will be replaced with real entity ID in tests
            "entity_type": fake.random_element(elements=[
                EntityType.TEST.value, EntityType.TEST_SET.value, EntityType.TEST_RUN.value, 
                EntityType.TEST_RESULT.value, EntityType.METRIC.value, EntityType.MODEL.value, 
                EntityType.PROMPT.value, EntityType.BEHAVIOR.value, EntityType.CATEGORY.value
            ])
        }
    
    @classmethod
    def sample_data(cls, entity_id: Optional[str] = None, entity_type: str = None) -> Dict[str, Any]:
        """
        Generate sample comment data
        
        Args:
            entity_id: Optional entity ID (will use fake UUID if not provided)
            entity_type: Type of entity the comment belongs to
            
        Returns:
            Dict containing comment test data
        """
        return {
            "content": fake.paragraph(nb_sentences=2),
            "entity_id": entity_id or fake.uuid4(),  # Will be replaced with real entity ID in tests
            "entity_type": entity_type or EntityType.TEST.value,
            "emojis": {}  # Start with no emoji reactions
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate comment update data"""
        return {
            "content": fake.paragraph(nb_sentences=3)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate comment edge case data"""
        if case_type == "long_content":
            return {
                "content": fake.text(max_nb_chars=2000),
                "entity_id": fake.uuid4(),
                "entity_type": EntityType.TEST.value
            }
        elif case_type == "special_chars":
            return {
                "content": f"Comment with émojis 💬 and spëcial chars! @#$%^&*()",
                "entity_id": fake.uuid4(),
                "entity_type": EntityType.TEST.value
            }
        elif case_type == "unicode":
            return {
                "content": f"Comment 测试 тест テスト {fake.sentence()}",
                "entity_id": fake.uuid4(),
                "entity_type": EntityType.TEST.value
            }
        elif case_type == "empty_content":
            return {
                "content": "",
                "entity_id": fake.uuid4(),
                "entity_type": EntityType.TEST.value
            }
        elif case_type == "sql_injection":
            return {
                "content": "'; DROP TABLE comments; --",
                "entity_id": fake.uuid4(),
                "entity_type": EntityType.TEST.value
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def with_emoji_reactions(cls, emoji_reactions: Dict[str, List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Generate comment data with emoji reactions
        
        Args:
            emoji_reactions: Dict of emoji reactions in format {emoji: [list_of_user_reactions]}
            
        Returns:
            Dict containing comment data with emoji reactions
        """
        if emoji_reactions is None:
            # Default emoji reactions for testing
            emoji_reactions = {
                "🚀": [
                    {"user_id": str(fake.uuid4()), "user_name": fake.name()},
                    {"user_id": str(fake.uuid4()), "user_name": fake.name()}
                ],
                "👍": [
                    {"user_id": str(fake.uuid4()), "user_name": fake.name()}
                ]
            }
        
        data = cls.sample_data()
        data["emojis"] = emoji_reactions
        return data
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True, entity_type: str = "Test") -> List[Dict[str, Any]]:
        """
        Generate batch of comment data
        
        Args:
            count: Number of comment records to generate
            variation: Whether to vary the data or use similar patterns
            entity_type: Entity type for all comments
            
        Returns:
            List of comment data dictionaries
        """
        comments = []
        for i in range(count):
            if variation:
                # Create varied data
                data = cls.sample_data(
                    entity_type=fake.random_element(elements=["Test", "TestSet", "TestRun", "Behavior", "Metric"])
                )
            else:
                # Create similar data with incremental content
                data = {
                    "content": f"Test comment {i+1}: {fake.sentence()}",
                    "entity_id": fake.uuid4(),
                    "entity_type": entity_type,
                    "emojis": {}
                }
            comments.append(data)
        
        return comments


@dataclass
class TestDataFactory(BaseDataFactory):
    """Factory for generating test entity test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal test data (only required fields)"""
        # Test entity only requires organization_id and user_id (from OrganizationMixin)
        # All other fields are optional
        return {}
    
    @classmethod
    def sample_data(cls, include_prompt: bool = True, include_behavior: bool = True, 
                   include_category: bool = True, include_status: bool = True) -> Dict[str, Any]:
        """
        Generate sample test data
        
        Args:
            include_prompt: Whether to include prompt_id reference
            include_behavior: Whether to include behavior_id reference
            include_category: Whether to include category_id reference
            include_status: Whether to include status_id reference
            
        Returns:
            Dict containing test data
        """
        data = {}
        
        # Optional fields that can be included
        if include_prompt:
            data["prompt_id"] = None  # Will be set by fixtures
        
        if include_behavior:
            data["behavior_id"] = None  # Will be set by fixtures
            
        if include_category:
            data["category_id"] = None  # Will be set by fixtures
            
        if include_status:
            data["status_id"] = None  # Will be set by fixtures
        
        # Other optional fields
        data.update({
            "priority": fake.random_int(min=1, max=5),
            "test_metadata": {
                "source": fake.random_element(["manual", "automated", "imported"]),
                "tags": fake.words(nb=3),
                "notes": fake.sentence()
            }
        })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate test update data"""
        return {
            "priority": fake.random_int(min=1, max=5),
            "test_metadata": {
                "updated": True,
                "notes": fake.sentence(),
                "tags": fake.words(nb=2)
            }
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate test edge case data"""
        if case_type == "high_priority":
            return {
                "priority": 1,
                "test_metadata": {
                    "priority_reason": "Critical security test"
                }
            }
        elif case_type == "low_priority":
            return {
                "priority": 5,
                "test_metadata": {
                    "priority_reason": "Nice to have test"
                }
            }
        elif case_type == "complex_metadata":
            return {
                "test_metadata": {
                    "execution_context": {
                        "environment": "staging",
                        "browser": "chrome",
                        "viewport": {"width": 1920, "height": 1080}
                    },
                    "test_data": {
                        "inputs": fake.words(nb=5),
                        "expected_outputs": fake.words(nb=3)
                    },
                    "configuration": {
                        "timeout": 30000,
                        "retries": 3,
                        "parallel": True
                    }
                }
            }
        
        return super().edge_case_data(case_type)


@dataclass
class TagDataFactory(BaseDataFactory):
    """Factory for generating tag test data"""
    
    @classmethod
    def minimal_data(cls) -> Dict[str, Any]:
        """Generate minimal tag data (only required fields)"""
        return {
            "name": fake.word().title()
        }
    
    @classmethod
    def sample_data(cls, include_optional: bool = True) -> Dict[str, Any]:
        """Generate sample tag data"""
        data = {
            "name": fake.word().title()
        }
        
        if include_optional:
            # Unicode icons/emojis for tags
            icons = ["🏷️", "📌", "⭐", "🔖", "📋", "🎯", "💼", "🔍", "📊", "⚡", "🎨", "🔧"]
            data.update({
                "icon_unicode": fake.random_element(elements=icons)
            })
        
        return data
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate tag update data"""
        icons = ["🏷️", "📌", "⭐", "🔖", "📋", "🎯", "💼", "🔍", "📊", "⚡", "🎨", "🔧"]
        return {
            "name": fake.word().title(),
            "icon_unicode": fake.random_element(elements=icons)
        }
    
    @classmethod
    def edge_case_data(cls, case_type: str) -> Dict[str, Any]:
        """Generate tag edge case data"""
        if case_type == "long_name":
            return {
                "name": fake.text(max_nb_chars=200).replace('\n', ' '),
                "icon_unicode": "📋"
            }
        elif case_type == "special_chars":
            return {
                "name": f"Tag with émojis 🏷️ and spëcial chars! @#$%^&*()",
                "icon_unicode": "🏷️"
            }
        elif case_type == "unicode":
            return {
                "name": f"Tag 测试 тест テスト {fake.word()}",
                "icon_unicode": "🌍"
            }
        elif case_type == "common_tags":
            common_names = ["Important", "Urgent", "Review", "Draft", "Complete", "In Progress", "Bug", "Feature"]
            return {
                "name": fake.random_element(elements=common_names),
                "icon_unicode": fake.random_element(elements=["⭐", "🔥", "📋", "✅"])
            }
        
        return super().edge_case_data(case_type)
    
    @classmethod
    def batch_data(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """
        Generate batch of tag data
        
        Args:
            count: Number of tag records to generate
            variation: Whether to vary the data or use similar patterns
            
        Returns:
            List of tag data dictionaries
        """
        tags = []
        for i in range(count):
            if variation:
                # Create varied data
                data = cls.sample_data(
                    include_optional=fake.boolean(),
                )
            else:
                # Create similar data with incremental names
                data = {
                    "name": f"Tag {i+1}",
                    "icon_unicode": "🏷️"
                }
            tags.append(data)
        
        return tags


# Update factory registry with new factories
FACTORY_REGISTRY.update({
    "comment": CommentDataFactory,
    "prompt_template": PromptTemplateDataFactory,
    "response_pattern": ResponsePatternDataFactory,
    "risk": RiskDataFactory,
    "source": SourceDataFactory,
    "status": StatusDataFactory,
    "tag": TagDataFactory,
    "test": TestDataFactory,
    "token": TokenDataFactory,
    "topic": TopicDataFactory,
    "type_lookup": TypeLookupDataFactory,
    "use_case": UseCaseDataFactory,
})


# Export main classes and functions
__all__ = [
    "BaseDataFactory",
    "BehaviorDataFactory",
    "TopicDataFactory", 
    "CategoryDataFactory",
    "CommentDataFactory",
    "EndpointDataFactory",
    "MetricDataFactory",
    "ModelDataFactory",
    "OrganizationDataFactory",
    "DimensionDataFactory",
    "PromptTemplateDataFactory",
    "ResponsePatternDataFactory", 
    "RiskDataFactory",
    "SourceDataFactory",
    "StatusDataFactory",
    "TagDataFactory",
    "TestDataFactory",
    "TokenDataFactory",
    "TopicDataFactory",
    "TypeLookupDataFactory",
    "UseCaseDataFactory",
    "FACTORY_REGISTRY",
    "get_factory",
    "generate_test_data"
]

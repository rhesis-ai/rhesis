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
        """Generate minimal metric data"""
        return {
            "name": fake.word().title() + " Metric"
        }
    
    @classmethod
    def sample_data(cls) -> Dict[str, Any]:
        """Generate sample metric data"""
        return {
            "name": fake.word().title() + " " + fake.word().title() + " Metric",
            "description": fake.text(max_nb_chars=150),
            "evaluation_prompt": fake.sentence(nb_words=8),
            "score_type": fake.random_element(elements=("numeric", "categorical", "binary"))
        }
    
    @classmethod
    def update_data(cls) -> Dict[str, Any]:
        """Generate metric update data"""
        return {
            "name": fake.bs().title() + " Metric",
            "description": fake.paragraph(nb_sentences=2),
            "evaluation_prompt": fake.sentence(nb_words=10)
        }


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


# Factory registry for dynamic access
FACTORY_REGISTRY = {
    "behavior": BehaviorDataFactory,
    "topic": TopicDataFactory,
    "category": CategoryDataFactory,
    "metric": MetricDataFactory,
    "dimension": DimensionDataFactory,
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
    "DimensionDataFactory",
    "FACTORY_REGISTRY",
    "get_factory",
    "generate_test_data"
]

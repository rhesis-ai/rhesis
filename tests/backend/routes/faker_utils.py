"""
🧪 Faker Utilities for Test Data Generation

This module provides consistent and realistic test data generation
using the Faker library for all route tests.

Usage:
    from tests.backend.routes.faker_utils import generate_behavior_data, generate_topic_data

Features:
- Consistent data generation patterns across all test files
- Realistic test data for better testing scenarios
- Domain-specific data generators for each entity type
- Special case generators for edge testing
"""

from faker import Faker
from typing import Dict, Any, Optional, List
import uuid

# Initialize Faker instance with consistent seed for reproducible tests
fake = Faker()
Faker.seed(12345)  # Consistent seed for reproducible test data


class TestDataGenerator:
    """Central class for generating test data with Faker"""

    @staticmethod
    def generate_behavior_data(
        include_optional: bool = True, long_name: bool = False, special_chars: bool = False
    ) -> Dict[str, Any]:
        """
        Generate realistic behavior test data

        Args:
            include_optional: Include optional fields
            long_name: Generate very long name for edge testing
            special_chars: Include special characters for edge testing

        Returns:
            Dict containing behavior data
        """
        if long_name:
            name = fake.text(max_nb_chars=1000).replace("\n", " ")
        elif special_chars:
            name = f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}"
        else:
            name = fake.catch_phrase()

        data = {
            "name": name,
            "description": fake.text(max_nb_chars=200) if include_optional else None,
        }

        if include_optional:
            data.update({"status_id": None, "user_id": None, "organization_id": None})

        return data

    @staticmethod
    def generate_behavior_update_data() -> Dict[str, Any]:
        """Generate behavior update data"""
        return {
            "name": fake.sentence(nb_words=3).rstrip("."),
            "description": fake.paragraph(nb_sentences=2),
        }

    @staticmethod
    def generate_behavior_minimal() -> Dict[str, Any]:
        """Generate minimal behavior data"""
        return {"name": fake.word().title() + " " + fake.bs().title()}

    @staticmethod
    def generate_metric_data() -> Dict[str, Any]:
        """Generate realistic metric test data"""
        score_type = fake.random_element(elements=("numeric", "categorical"))
        data = {
            "name": fake.word().title() + " " + fake.word().title(),
            "description": fake.text(max_nb_chars=150),
            "evaluation_prompt": fake.sentence(nb_words=8),
            "score_type": score_type,
        }

        # Add required fields for categorical metrics
        if score_type == "categorical":
            data["categories"] = ["pass", "fail", "partial"]
            data["passing_categories"] = ["pass"]

        return data

    @staticmethod
    def generate_topic_data(
        include_optional: bool = True,
        long_name: bool = False,
        special_chars: bool = False,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate realistic topic test data

        Args:
            include_optional: Include optional fields
            long_name: Generate very long name for edge testing
            special_chars: Include special characters for edge testing
            parent_id: Parent topic ID for hierarchical testing

        Returns:
            Dict containing topic data
        """
        if long_name:
            name = fake.text(max_nb_chars=1000).replace("\n", " ")
        elif special_chars:
            name = f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}"
        else:
            name = fake.catch_phrase()

        data = {
            "name": name,
            "description": fake.text(max_nb_chars=200) if include_optional else None,
        }

        if include_optional:
            data.update(
                {
                    "parent_id": parent_id,
                    "entity_type_id": None,
                    "status_id": None,
                    "organization_id": None,
                    "user_id": None,
                }
            )

        return data

    @staticmethod
    def generate_topic_update_data() -> Dict[str, Any]:
        """Generate topic update data"""
        return {
            "name": fake.sentence(nb_words=3).rstrip("."),
            "description": fake.paragraph(nb_sentences=2),
        }

    @staticmethod
    def generate_topic_minimal() -> Dict[str, Any]:
        """Generate minimal topic data"""
        return {"name": fake.word().title() + " " + fake.word().title()}

    @staticmethod
    def generate_parent_topic_data() -> Dict[str, Any]:
        """Generate parent topic data for hierarchical testing"""
        return {
            "name": fake.sentence(nb_words=2).rstrip(".") + " Topic",
            "description": fake.text(max_nb_chars=100),
        }

    @staticmethod
    def generate_child_topic_data(parent_id: str) -> Dict[str, Any]:
        """Generate child topic data for hierarchical testing"""
        return {
            "name": fake.word().title() + " Child Topic",
            "description": fake.text(max_nb_chars=120),
            "parent_id": parent_id,
        }

    @staticmethod
    def generate_performance_test_data(entity_type: str, count: int) -> List[Dict[str, Any]]:
        """
        Generate multiple test data entries for performance testing

        Args:
            entity_type: Type of entity ('behavior' or 'topic')
            count: Number of entries to generate

        Returns:
            List of test data dictionaries
        """
        data_list = []

        for i in range(count):
            if entity_type == "behavior":
                data = {
                    "name": f"{fake.word().title()} Test Behavior {i}",
                    "description": fake.paragraph(nb_sentences=2),
                }
            elif entity_type == "topic":
                data = {
                    "name": f"{fake.word().title()} Performance Test Topic {i}",
                    "description": fake.paragraph(nb_sentences=2),
                }
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")

            data_list.append(data)

        return data_list

    @staticmethod
    def generate_random_uuid() -> str:
        """Generate random UUID for testing"""
        return str(uuid.uuid4())

    @staticmethod
    def generate_invalid_data() -> Dict[str, Any]:
        """Generate invalid data for error testing"""
        return {}  # Missing required fields

    @staticmethod
    def generate_null_description_data(entity_type: str) -> Dict[str, Any]:
        """Generate data with explicit null description"""
        return {"name": fake.catch_phrase(), "description": None}

    @staticmethod
    def generate_empty_description_data(entity_type: str) -> Dict[str, Any]:
        """Generate data with empty string description"""
        return {"name": fake.catch_phrase(), "description": ""}

    @staticmethod
    def generate_category_data(
        include_optional: bool = True, long_name: bool = False, special_chars: bool = False
    ) -> Dict[str, Any]:
        """
        Generate realistic category test data

        Args:
            include_optional: Include optional fields
            long_name: Generate very long name for edge testing
            special_chars: Include special characters for edge testing

        Returns:
            Dict containing category data
        """
        if long_name:
            name = fake.text(max_nb_chars=1000).replace("\n", " ") + " Category"
        elif special_chars:
            name = f"{fake.word()} 🏷️ Category with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}"
        else:
            name = fake.word().title() + " " + fake.word().title() + " Category"

        data = {
            "name": name,
        }

        if include_optional:
            data.update(
                {
                    "description": fake.text(max_nb_chars=200),
                    "parent_id": None,
                    "entity_type_id": None,
                    "status_id": None,
                    "organization_id": None,
                    "user_id": None,
                }
            )

        return data

    @staticmethod
    def generate_category_update_data() -> Dict[str, Any]:
        """Generate category update data"""
        return {
            "name": fake.sentence(nb_words=2).rstrip(".") + " Category",
            "description": fake.paragraph(nb_sentences=2),
        }

    @staticmethod
    def generate_category_minimal() -> Dict[str, Any]:
        """Generate minimal category data"""
        return {"name": fake.word().title() + " Category"}

    @staticmethod
    def generate_dimension_data(
        include_optional: bool = True, long_name: bool = False, special_chars: bool = False
    ) -> Dict[str, Any]:
        """
        Generate realistic dimension test data

        Args:
            include_optional: Include optional fields
            long_name: Generate very long name for edge testing
            special_chars: Include special characters for edge testing

        Returns:
            Dict containing dimension data
        """
        if long_name:
            name = fake.text(max_nb_chars=1000).replace("\n", " ")
        elif special_chars:
            name = f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}"
        else:
            name = fake.word().title() + " Dimension"

        data = {
            "name": name,
            "description": fake.text(max_nb_chars=200) if include_optional else None,
        }

        if include_optional:
            data.update({"user_id": None, "organization_id": None})

        return data

    @staticmethod
    def generate_dimension_update_data() -> Dict[str, Any]:
        """Generate dimension update data"""
        return {
            "name": fake.sentence(nb_words=2).rstrip(".") + " Dimension",
            "description": fake.paragraph(nb_sentences=2),
        }

    @staticmethod
    def generate_dimension_minimal() -> Dict[str, Any]:
        """Generate minimal dimension data"""
        return {"name": fake.word().title() + " Dimension"}

    @staticmethod
    def generate_demographic_data(
        include_optional: bool = True,
        long_name: bool = False,
        special_chars: bool = False,
        dimension_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate realistic demographic test data

        Args:
            include_optional: Include optional fields
            long_name: Generate very long name for edge testing
            special_chars: Include special characters for edge testing
            dimension_id: Dimension ID for relationship testing

        Returns:
            Dict containing demographic data
        """
        if long_name:
            name = fake.text(max_nb_chars=1000).replace("\n", " ")
        elif special_chars:
            name = f"{fake.word()} 🧪 with émoji & spëcial chars! {fake.random_element(elements=['@', '#', '$', '%'])}"
        else:
            name = fake.word().title() + " Demographic"

        data = {
            "name": name,
            "description": fake.text(max_nb_chars=200) if include_optional else None,
        }

        if include_optional:
            data.update({"dimension_id": dimension_id, "user_id": None, "organization_id": None})

        return data

    @staticmethod
    def generate_demographic_update_data() -> Dict[str, Any]:
        """Generate demographic update data"""
        return {
            "name": fake.sentence(nb_words=2).rstrip(".") + " Demographic",
            "description": fake.paragraph(nb_sentences=2),
        }

    @staticmethod
    def generate_demographic_minimal() -> Dict[str, Any]:
        """Generate minimal demographic data"""
        return {"name": fake.word().title() + " Demographic"}


# Convenience functions for backward compatibility and ease of use
def generate_behavior_data(**kwargs) -> Dict[str, Any]:
    """Convenience function for generating behavior data"""
    return TestDataGenerator.generate_behavior_data(**kwargs)


def generate_topic_data(**kwargs) -> Dict[str, Any]:
    """Convenience function for generating topic data"""
    return TestDataGenerator.generate_topic_data(**kwargs)


def generate_category_data(**kwargs) -> Dict[str, Any]:
    """Convenience function for generating category data"""
    return TestDataGenerator.generate_category_data(**kwargs)


def generate_metric_data() -> Dict[str, Any]:
    """Convenience function for generating metric data"""
    return TestDataGenerator.generate_metric_data()


def generate_random_uuid() -> str:
    """Convenience function for generating random UUID"""
    return TestDataGenerator.generate_random_uuid()


def generate_dimension_data(**kwargs) -> Dict[str, Any]:
    """Convenience function for generating dimension data"""
    return TestDataGenerator.generate_dimension_data(**kwargs)


def generate_demographic_data(**kwargs) -> Dict[str, Any]:
    """Convenience function for generating demographic data"""
    return TestDataGenerator.generate_demographic_data(**kwargs)

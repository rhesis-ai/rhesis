"""
🔍 User Field Auto-Detection

This module provides intelligent auto-detection of user relationship fields
(user_id, owner_id, assignee_id) for entity test classes using multiple strategies.
"""

from typing import Any, Dict, Set


class UserFieldDetector:
    """Intelligent detector for user relationship fields"""

    @classmethod
    def detect_user_fields(cls, test_class) -> Set[str]:
        """
        Detect user relationship fields using multiple strategies

        Args:
            test_class: The test class to analyze

        Returns:
            Set of detected user field names
        """
        detected_fields = set()

        # Strategy 1: Check common field naming patterns first (fastest)
        detected_fields.update(cls._detect_from_naming_patterns(test_class))

        # Strategy 2: Try to introspect from model (if entity name maps to a model)
        detected_fields.update(cls._detect_from_model_introspection(test_class))

        return detected_fields

    @classmethod
    def _detect_from_naming_patterns(cls, test_class) -> Set[str]:
        """Detect user fields based on common naming patterns for the entity"""
        detected = set()

        # For certain entity types, we can make educated guesses based on actual model definitions
        entity_user_field_mapping = {
            # Entities with OrganizationAndUserMixin (user_id only)
            "behavior": ["user_id"],
            "category": ["user_id"],
            "demographic": ["user_id"],
            "dimension": ["user_id"],
            "status": ["user_id"],
            "topic": ["user_id"],
            "type_lookup": ["user_id"],
            # Entities with explicit user relationship fields
            "test": ["user_id", "owner_id", "assignee_id"],
            "test_run": ["user_id", "owner_id", "assignee_id"],
            "test_set": ["owner_id", "assignee_id"],  # Has user_id from relationship
            "metric": ["user_id", "owner_id", "assignee_id"],  # UserOwnedMixin + explicit fields
            "model": ["user_id", "owner_id", "assignee_id"],
            "project": ["user_id", "owner_id"],
            "prompt": ["user_id"],  # Explicit user_id field
            "organization": ["owner_id", "user_id"],  # Explicit fields
            # Entities with OrganizationMixin only (no user fields)
            "prompt_template": [],  # OrganizationMixin but no user fields in our tests
            "test_configuration": [],  # OrganizationMixin but no user fields in our tests
            # Entities with explicit user_id field
            "endpoint": ["user_id"],  # Has explicit user_id field
        }

        if (
            hasattr(test_class, "entity_name")
            and test_class.entity_name in entity_user_field_mapping
        ):
            detected.update(entity_user_field_mapping[test_class.entity_name])

        return detected

    @classmethod
    def _detect_from_model_introspection(cls, test_class) -> Set[str]:
        """Try to introspect the actual SQLAlchemy model if available"""
        detected = set()

        try:
            if not hasattr(test_class, "entity_name"):
                return detected

            # Attempt to import and inspect the model
            # This is a best-effort attempt that may not always work
            model_name = test_class.entity_name.title()

            # Try different import paths where models might be located
            import_paths = [
                f"rhesis.backend.app.models.{test_class.entity_name}",
                "rhesis.backend.app.models",
                f"apps.backend.src.rhesis.backend.app.models.{test_class.entity_name}",
                "apps.backend.src.rhesis.backend.app.models",
            ]

            model_class = None
            for import_path in import_paths:
                try:
                    if "." in import_path:
                        module_path, class_name = import_path, model_name
                    else:
                        module_path, class_name = import_path, model_name

                    module = __import__(module_path, fromlist=[class_name])
                    model_class = getattr(module, class_name, None)
                    if model_class:
                        break
                except (ImportError, AttributeError):
                    continue

            if model_class and hasattr(model_class, "__table__"):
                # Inspect SQLAlchemy model columns
                for column in model_class.__table__.columns:
                    column_name = column.name
                    if column_name in ["user_id", "owner_id", "assignee_id"]:
                        detected.add(column_name)
                    elif column_name.endswith("_user_id") or (
                        column_name.endswith("_id") and "user" in column_name
                    ):
                        detected.add(column_name)

                # Check for foreign keys to user table
                for column in model_class.__table__.columns:
                    if hasattr(column, "foreign_keys"):
                        for fk in column.foreign_keys:
                            if "user." in str(fk.target_fullname) or str(
                                fk.target_fullname
                            ).endswith(".user.id"):
                                detected.add(column.name)

        except Exception:
            # Model introspection failed, which is okay
            pass

        return detected

    @classmethod
    def _detect_from_sample_data(cls, test_class, sample_data: Dict[str, Any]) -> Set[str]:
        """Detect user fields from sample data structure"""
        detected = set()

        for key in sample_data.keys():
            if key in ["user_id", "owner_id", "assignee_id"]:
                detected.add(key)
            elif key.endswith("_user_id"):
                detected.add(key)
            elif "user" in key and key.endswith("_id"):
                detected.add(key)

        return detected

    @classmethod
    def _detect_from_endpoint_schema(cls, test_class) -> Set[str]:
        """Try to detect user fields from API endpoint schemas"""
        detected = set()

        try:
            # This could potentially make a request to get the OpenAPI schema
            # and analyze it for user relationship fields, but for now we'll
            # keep this as a placeholder for future enhancement
            pass
        except Exception:
            pass

        return detected

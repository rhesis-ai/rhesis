import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import (
    DEFAULT_BATCH_SIZE,
    ERROR_BULK_CREATE_FAILED,
    EntityType,
)
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_entity,
    get_or_create_status,
    get_or_create_type_lookup,
)
from rhesis.backend.app.utils.uuid_utils import (
    ensure_owner_id,
    sanitize_uuid_field,
    validate_uuid_parameters,
)
from rhesis.backend.logging import logger


class _BulkEntityCache:
    """
    In-memory cache for entity lookups during bulk operations.

    Dramatically reduces database round-trips when creating many tests
    with the same topic/behavior/category (common in Garak imports).

    Usage:
        cache = _BulkEntityCache()
        topic = cache.get_or_create_topic(db, name, defaults, org_id, user_id)
    """

    def __init__(self):
        self.topics: Dict[str, models.Topic] = {}
        self.behaviors: Dict[str, models.Behavior] = {}
        self.categories: Dict[str, models.Category] = {}
        self.statuses: Dict[tuple, models.Status] = {}
        self.type_lookups: Dict[tuple, models.TypeLookup] = {}

    def get_or_create_topic(
        self,
        db: Session,
        name: str,
        defaults: Dict,
        organization_id: str,
        user_id: str,
    ) -> models.Topic:
        """Get or create a topic, using cache if available."""
        cache_key = name
        if cache_key in self.topics:
            return self.topics[cache_key]

        # Cache miss - use existing get_or_create_entity logic
        topic = _create_entity_with_status_uncached(
            db=db,
            model=models.Topic,
            name=name,
            defaults=defaults,
            entity_type=EntityType.TOPIC,
            organization_id=organization_id,
            user_id=user_id,
        )
        self.topics[cache_key] = topic
        return topic

    def get_or_create_behavior(
        self,
        db: Session,
        name: str,
        defaults: Dict,
        organization_id: str,
        user_id: str,
    ) -> models.Behavior:
        """Get or create a behavior, using cache if available."""
        cache_key = name
        if cache_key in self.behaviors:
            return self.behaviors[cache_key]

        behavior = _create_entity_with_status_uncached(
            db=db,
            model=models.Behavior,
            name=name,
            defaults=defaults,
            entity_type=EntityType.BEHAVIOR,
            organization_id=organization_id,
            user_id=user_id,
        )
        self.behaviors[cache_key] = behavior
        return behavior

    def get_or_create_category(
        self,
        db: Session,
        name: str,
        defaults: Dict,
        organization_id: str,
        user_id: str,
    ) -> models.Category:
        """Get or create a category, using cache if available."""
        cache_key = name
        if cache_key in self.categories:
            return self.categories[cache_key]

        category = _create_entity_with_status_uncached(
            db=db,
            model=models.Category,
            name=name,
            defaults=defaults,
            entity_type=EntityType.CATEGORY,
            organization_id=organization_id,
            user_id=user_id,
        )
        self.categories[cache_key] = category
        return category

    def get_or_create_status(
        self,
        db: Session,
        name: str,
        entity_type: EntityType,
        organization_id: str,
        user_id: str,
    ) -> models.Status:
        """Get or create a status, using cache if available."""
        cache_key = (name, entity_type.value if hasattr(entity_type, "value") else entity_type)
        if cache_key in self.statuses:
            return self.statuses[cache_key]

        status = get_or_create_status(
            db=db,
            name=name,
            entity_type=entity_type,
            organization_id=organization_id,
            user_id=user_id,
        )
        self.statuses[cache_key] = status
        return status

    def get_or_create_type_lookup(
        self,
        db: Session,
        type_name: str,
        type_value: str,
        organization_id: str,
        user_id: str,
    ) -> models.TypeLookup:
        """Get or create a type lookup, using cache if available."""
        cache_key = (type_name, type_value)
        if cache_key in self.type_lookups:
            return self.type_lookups[cache_key]

        type_lookup = get_or_create_type_lookup(
            db=db,
            type_name=type_name,
            type_value=type_value,
            organization_id=organization_id,
            user_id=user_id,
        )
        self.type_lookups[cache_key] = type_lookup
        return type_lookup


def load_defaults():
    """Load default values from bulk_defaults.json"""
    defaults_path = Path(__file__).parent / "bulk_defaults.json"
    with open(defaults_path) as f:
        return json.load(f)


def _validate_test_set(
    db: Session, test_set_id: str, organization_id: str = None
) -> tuple[models.TestSet | None, Dict[str, Any] | None]:
    """Validate test set exists and return it or error response."""
    query = db.query(models.TestSet).filter(models.TestSet.id == test_set_id)

    # Apply organization filter if provided (SECURITY CRITICAL)
    if organization_id:
        from uuid import UUID

        query = query.filter(models.TestSet.organization_id == UUID(organization_id))

    test_set = query.first()
    if not test_set:
        return None, {
            "success": False,
            "total_tests": 0,
            "message": f"Test set with ID {test_set_id} not found or not accessible",
        }
    return test_set, None


def _categorize_test_ids(
    db: Session, test_ids: List[str], test_set_id: str, organization_id: str
) -> tuple[set[str], set[str], set[str]]:
    """
    Categorize test IDs into existing, missing, and already associated.
    Returns (existing_test_ids, missing_test_ids, already_associated_ids)
    """
    # Convert input test_ids to a set of strings
    test_id_set = {str(id_).lower() for id_ in test_ids}

    # Find existing tests AND ensure they belong to the organization (SECURITY CRITICAL)
    from uuid import UUID

    existing_tests = (
        db.query(models.Test)
        .filter(models.Test.id.in_(test_ids), models.Test.organization_id == UUID(organization_id))
        .all()
    )
    existing_test_ids = {str(test.id).lower() for test in existing_tests}
    missing_test_ids = test_id_set - existing_test_ids

    # Find already associated tests
    already_associated = db.execute(
        test_test_set_association.select().where(
            test_test_set_association.c.test_set_id == test_set_id,
            test_test_set_association.c.test_id.in_(
                list(existing_test_ids)
            ),  # Only check among existing tests
            test_test_set_association.c.organization_id == organization_id,
        )
    ).fetchall()
    already_associated_ids = {str(assoc.test_id).lower() for assoc in already_associated}

    return existing_test_ids, missing_test_ids, already_associated_ids


def _build_response_message(
    new_associations: int, missing_count: int, already_associated_count: int
) -> str:
    """Build a response message based on association results.

    Args:
        new_associations: Number of new associations created
        missing_count: Number of test IDs that don't exist
        already_associated_count: Number of tests already associated

    Returns:
        A descriptive message based on the combination of counts
    """
    total = new_associations + missing_count + already_associated_count

    # Case: All tests were successfully associated
    if new_associations == total and missing_count == 0 and already_associated_count == 0:
        plural = "s" if new_associations != 1 else ""
        return f"Successfully associated {new_associations} new test{plural}."

    # Case: All tests were missing
    if missing_count == total and new_associations == 0 and already_associated_count == 0:
        plural = "s" if missing_count != 1 else ""
        return f"No tests were associated. All {missing_count} test{plural} could not be found."

    # Case: All tests were already associated
    if already_associated_count == total and new_associations == 0 and missing_count == 0:
        plural = "s" if already_associated_count != 1 else ""
        return (
            f"No new tests were associated. All {already_associated_count} "
            f"test{plural} were already associated."
        )

    # Mixed cases
    parts = []

    if new_associations > 0:
        plural = "s" if new_associations != 1 else ""
        parts.append(f"Successfully associated {new_associations} new test{plural}")

    if already_associated_count > 0:
        verb = "s were" if already_associated_count != 1 else " was"
        parts.append(f"{already_associated_count} test{verb} already associated")

    if missing_count > 0:
        parts.append(f"{missing_count} test{'s' if missing_count != 1 else ''} could not be found")

    # Join the parts with appropriate punctuation
    if len(parts) == 1:
        return f"{parts[0]}."
    elif len(parts) == 2:
        return f"{parts[0]} and {parts[1]}."
    else:
        return f"{', '.join(parts[:-1])}, and {parts[-1]}."


def bulk_create_test_set_associations(
    db: Session,
    test_ids: List[str],
    test_set_id: str,
    organization_id: str,
    user_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    """
    Bulk create associations between tests and a test set in batches.
    Handles validation of test IDs and existing associations.
    """
    # First validate the test set exists AND belongs to organization (SECURITY CRITICAL)
    test_set, error_response = _validate_test_set(db, test_set_id, organization_id)
    if error_response:
        return error_response

    # Categorize the test IDs
    existing_test_ids, missing_test_ids, already_associated_ids = _categorize_test_ids(
        db=db, test_ids=test_ids, test_set_id=test_set_id, organization_id=organization_id
    )

    # Calculate tests to be associated (existing tests that aren't already associated)
    to_associate = existing_test_ids - already_associated_ids

    # Create new associations in batches
    new_associations_count = 0
    if to_associate:
        for i in range(0, len(to_associate), batch_size):
            batch = list(to_associate)[i : i + batch_size]
            association_records = [
                {
                    "test_id": test_id,
                    "test_set_id": test_set_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                }
                for test_id in batch
            ]
            db.execute(test_test_set_association.insert(), association_records)
            new_associations_count += len(batch)
            db.flush()

    message = _build_response_message(
        new_associations=new_associations_count,
        missing_count=len(missing_test_ids),
        already_associated_count=len(already_associated_ids),
    )

    # Set success to False if no new associations were created
    success = new_associations_count > 0

    return {
        "success": success,
        "total_tests": len(test_ids),
        "message": message,
        "metadata": {
            "new_associations": new_associations_count,
            "existing_associations": len(already_associated_ids),
            "invalid_associations": len(missing_test_ids),
            "existing_test_ids": list(existing_test_ids),
            "invalid_test_ids": list(missing_test_ids),
        },
    }


def _create_entity_with_status_uncached(
    db: Session,
    model: Any,
    name: str,
    defaults: Dict,
    entity_type: EntityType,
    organization_id: str,
    user_id: str,
    **extra_fields,
) -> Any:
    """Helper to create an entity with a status (no caching)."""
    # Get the string value from EntityType enum and convert to lowercase
    entity_type_str = entity_type.value.lower()

    # Prepare base entity data
    entity_data = {
        "name": name,
        "organization_id": organization_id,
        "user_id": user_id,
        **extra_fields,
    }

    # Only add status_id if the model has a status_id field
    if hasattr(model, "status_id"):
        status = get_or_create_status(
            db=db,
            name=defaults[entity_type_str]["status"],
            entity_type=EntityType.GENERAL,
            organization_id=organization_id,
            user_id=user_id,
        )
        entity_data["status_id"] = status.id

    return get_or_create_entity(
        db=db,
        model=model,
        entity_data=entity_data,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_entity_with_status(
    db: Session,
    model: Any,
    name: str,
    defaults: Dict,
    entity_type: EntityType,
    organization_id: str,
    user_id: str,
    cache: _BulkEntityCache = None,
    **extra_fields,
) -> Any:
    """
    Helper to create an entity with a status.

    Args:
        cache: Optional _BulkEntityCache for caching lookups in bulk operations.
               When provided, dramatically reduces DB round-trips for repeated values.
    """
    # Use cache if provided and entity type is cacheable
    if cache is not None:
        if model == models.Topic:
            return cache.get_or_create_topic(db, name, defaults, organization_id, user_id)
        elif model == models.Behavior:
            return cache.get_or_create_behavior(db, name, defaults, organization_id, user_id)
        elif model == models.Category:
            return cache.get_or_create_category(db, name, defaults, organization_id, user_id)

    # Fall back to uncached version
    return _create_entity_with_status_uncached(
        db=db,
        model=model,
        name=name,
        defaults=defaults,
        entity_type=entity_type,
        organization_id=organization_id,
        user_id=user_id,
        **extra_fields,
    )


def prepare_test_data(
    test_data: Dict[str, Any] | schemas.TestData, defaults: Dict
) -> Dict[str, Any]:
    """Convert and prepare test data for processing"""
    if hasattr(test_data, "model_dump"):
        data = test_data.model_dump()
    else:
        data = test_data.copy()

    # Debug: Log original data
    uuid_fields_before = {k: v for k, v in data.items() if k.endswith("_id")}
    logger.debug(f"prepare_test_data - UUID fields before sanitization: {uuid_fields_before}")

    # Sanitize UUID fields - convert empty strings to None
    for key, value in list(data.items()):
        if key.endswith("_id"):
            original_value = value
            data[key] = sanitize_uuid_field(value)
            if original_value != data[key]:
                logger.debug(
                    f"prepare_test_data - Sanitized {key}: '{original_value}' -> '{data[key]}'"
                )

    # Debug: Log sanitized data
    uuid_fields_after = {k: v for k, v in data.items() if k.endswith("_id")}
    logger.debug(f"prepare_test_data - UUID fields after sanitization: {uuid_fields_after}")

    return data


def create_prompt(
    db: Session, prompt_data: Dict, defaults: Dict, organization_id: str, user_id: str
) -> models.Prompt:
    """Create a prompt with its associated entities"""
    # Multi-turn tests don't have prompts, return None
    if not prompt_data:
        return None

    if hasattr(prompt_data, "model_dump"):
        prompt_data = prompt_data.model_dump()

    demographic = None
    if "demographic" in prompt_data and "dimension" in prompt_data:
        dimension = create_entity_with_status(
            db=db,
            model=models.Dimension,
            name=prompt_data.pop("dimension"),
            defaults=defaults,
            entity_type=EntityType.DIMENSION,
            organization_id=organization_id,
            user_id=user_id,
        )

        demographic = create_entity_with_status(
            db=db,
            model=models.Demographic,
            name=prompt_data.pop("demographic"),
            defaults=defaults,
            entity_type=EntityType.DEMOGRAPHIC,
            organization_id=organization_id,
            user_id=user_id,
            dimension_id=dimension.id,
        )

    return get_or_create_entity(
        db=db,
        model=models.Prompt,
        entity_data={
            **prompt_data,
            "organization_id": organization_id,
            "user_id": user_id,
            "status_id": get_or_create_status(
                db=db,
                name=defaults["prompt"]["status"],
                entity_type=EntityType.GENERAL,
                organization_id=organization_id,
                user_id=user_id,
            ).id,
            "language_code": prompt_data.get("language_code", defaults["prompt"]["language_code"]),
            "demographic_id": demographic.id if demographic else None,
            "expected_response": prompt_data.get("expected_response"),
        },
        organization_id=organization_id,
        user_id=user_id,
    )


def bulk_create_tests(
    db: Session,
    tests_data: List[Dict[str, Any] | schemas.TestData],
    organization_id: str,
    user_id: str,
    test_set_id: str | None = None,
    test_type_value: str | None = None,
) -> List[models.Test]:
    """Bulk create tests from a list of test data dictionaries or TestData objects.

    Args:
        db: Database session
        tests_data: List of test data
        organization_id: Organization ID
        user_id: User ID
        test_set_id: Optional test set ID
        test_type_value: Optional test type value (e.g., "Single-Turn", "Multi-Turn")
    """
    # Validate input UUIDs
    validation_error = validate_uuid_parameters(organization_id, user_id, test_set_id)
    if validation_error:
        error_msg = validation_error
        logger.error(error_msg)
        raise Exception(ERROR_BULK_CREATE_FAILED.format(entity="tests", error=error_msg))

    created_tests = []
    defaults = load_defaults()

    # Create cache for entity lookups - dramatically reduces DB round-trips
    # when many tests share the same topic/behavior/category (common in Garak imports)
    cache = _BulkEntityCache()

    try:
        # Cache the test status (used for all tests)
        test_status = cache.get_or_create_status(
            db=db,
            name=defaults["test"]["status"],
            entity_type=EntityType.TEST,
            organization_id=organization_id,
            user_id=user_id,
        )

        for i, test_data in enumerate(tests_data):
            logger.debug(f"bulk_create_tests - Processing test {i + 1}/{len(tests_data)}")
            test_data_dict = prepare_test_data(test_data, defaults)
            logger.debug(
                f"bulk_create_tests - test_data_dict after prepare_test_data: {test_data_dict}"
            )

            # Determine test type for this specific test
            # Priority: 1. Individual test's test_type, 2. Auto-detect from config,
            # 3. test_set's test_type_value, 4. defaults
            individual_test_type = test_data_dict.pop("test_type", None)

            # Auto-detect test type based on test_configuration
            # If test_configuration has a 'goal' field, it's a multi-turn test
            # If prompt is provided (and no goal in config), it's a single-turn test
            auto_detected_type = None
            test_config = test_data_dict.get("test_configuration", {})
            if test_config and isinstance(test_config, dict) and "goal" in test_config:
                auto_detected_type = "Multi-Turn"
            elif test_data_dict.get("prompt"):
                auto_detected_type = "Single-Turn"

            type_value_to_use = (
                individual_test_type
                or auto_detected_type
                or test_type_value
                or defaults["test"]["test_type"]
            )

            # Get or create test type for this specific test (cached)
            test_type = cache.get_or_create_type_lookup(
                db=db,
                type_name="TestType",
                type_value=type_value_to_use,
                organization_id=organization_id,
                user_id=user_id,
            )

            prompt_data = test_data_dict.pop("prompt", {})

            # Create prompt only for single-turn tests (when prompt_data is provided)
            # Multi-turn tests don't use prompts - they use test_configuration
            prompt = None
            if prompt_data:
                prompt = create_prompt(
                    db=db,
                    prompt_data=prompt_data,
                    defaults=defaults,
                    organization_id=organization_id,
                    user_id=user_id,
                )

            # Create topic, behavior, and category (with caching for bulk operations)
            topic = create_entity_with_status(
                db=db,
                model=models.Topic,
                name=test_data_dict.pop("topic"),
                defaults=defaults,
                entity_type=EntityType.TOPIC,
                organization_id=organization_id,
                user_id=user_id,
                cache=cache,
            )

            behavior = create_entity_with_status(
                db=db,
                model=models.Behavior,
                name=test_data_dict.pop("behavior"),
                defaults=defaults,
                entity_type=EntityType.BEHAVIOR,
                organization_id=organization_id,
                user_id=user_id,
                cache=cache,
            )

            category = create_entity_with_status(
                db=db,
                model=models.Category,
                name=test_data_dict.pop("category"),
                defaults=defaults,
                entity_type=EntityType.CATEGORY,
                organization_id=organization_id,
                user_id=user_id,
                cache=cache,
            )

            # Create test with improved owner_id handling
            original_assignee_id = test_data_dict.get("assignee_id", None)
            original_owner_id = test_data_dict.get("owner_id", None)
            logger.debug(
                f"bulk_create_tests - Original UUID values: "
                f"assignee_id='{original_assignee_id}', "
                f"owner_id='{original_owner_id}'"
            )

            assignee_id = sanitize_uuid_field(test_data_dict.pop("assignee_id", None))
            owner_id = ensure_owner_id(test_data_dict.pop("owner_id", None), user_id)

            logger.debug(
                f"bulk_create_tests - Sanitized UUID values: "
                f"assignee_id='{assignee_id}', "
                f"owner_id='{owner_id}'"
            )

            # Extract source_id from metadata if present
            # Note: SDK uses "metadata" but DB uses "test_metadata"
            source_id = None
            metadata_dict = test_data_dict.get("metadata") or test_data_dict.get("test_metadata")

            if isinstance(metadata_dict, dict):
                source_id = metadata_dict.get("_source_id")
                if source_id:
                    # Remove it from metadata before storing
                    if "metadata" in test_data_dict and isinstance(
                        test_data_dict["metadata"], dict
                    ):
                        test_data_dict["metadata"] = {
                            k: v for k, v in test_data_dict["metadata"].items() if k != "_source_id"
                        }
                    if "test_metadata" in test_data_dict and isinstance(
                        test_data_dict["test_metadata"], dict
                    ):
                        test_data_dict["test_metadata"] = {
                            k: v
                            for k, v in test_data_dict["test_metadata"].items()
                            if k != "_source_id"
                        }

            test_params = {
                "prompt_id": prompt.id if prompt else None,  # None for multi-turn tests
                "test_type_id": test_type.id,
                "topic_id": topic.id,
                "behavior_id": behavior.id,
                "category_id": category.id,
                "status_id": test_status.id
                if not test_data_dict.get("status")
                else get_or_create_status(
                    db=db,
                    name=test_data_dict.pop("status"),
                    entity_type=EntityType.TEST,
                    organization_id=organization_id,
                    user_id=user_id,
                ).id,
                "user_id": user_id,
                "organization_id": organization_id,
                "priority": test_data_dict.pop("priority", defaults["test"]["priority"]),
                "test_configuration": test_data_dict.pop(
                    "test_configuration", defaults["test"]["test_configuration"]
                ),
                "assignee_id": assignee_id,
                "owner_id": owner_id,
                "source_id": sanitize_uuid_field(source_id) if source_id else None,
            }

            # Clean any remaining UUID fields from the test data dict
            logger.debug(
                f"bulk_create_tests - Remaining test_data_dict before cleaning: {test_data_dict}"
            )
            for key, value in list(test_data_dict.items()):
                if key.endswith("_id"):
                    original_value = value
                    test_data_dict[key] = sanitize_uuid_field(value)
                    if original_value != test_data_dict[key]:
                        logger.debug(
                            f"bulk_create_tests - Cleaned remaining field {key}: "
                            f"'{original_value}' -> '{test_data_dict[key]}'"
                        )
            # Add any remaining fields from test_data_dict that weren't explicitly handled
            remaining_fields = {k: v for k, v in test_data_dict.items() if k not in test_params}
            logger.debug(f"bulk_create_tests - Remaining fields to add: {remaining_fields}")
            test_params.update(remaining_fields)

            # Log final test parameters for debugging UUID issues
            uuid_params = {k: v for k, v in test_params.items() if k.endswith("_id")}
            logger.debug(f"bulk_create_tests - Final UUID parameters: {uuid_params}")
            logger.debug(f"bulk_create_tests - All test parameters: {test_params}")
            # Map "metadata" to "test_metadata" (SDK uses "metadata" but DB uses "test_metadata")
            if "metadata" in test_params and "test_metadata" not in test_params:
                test_params["test_metadata"] = test_params.pop("metadata")

            try:
                test = models.Test(**test_params)
                db.add(test)
                created_tests.append(test)
                logger.debug(
                    f"bulk_create_tests - Successfully created Test model for test {i + 1}"
                )
            except Exception as model_error:
                logger.error(
                    f"bulk_create_tests - Failed to create Test model for test {i + 1}: "
                    f"{model_error}"
                )
                logger.error(
                    f"bulk_create_tests - Test parameters that caused error: {test_params}"
                )
                raise

            db.flush()

        # Create test set associations AFTER all tests are created (moved outside loop)
        # This fixes O(n²) behavior - previously called N times with growing list
        if test_set_id and created_tests:
            test_ids = [str(test.id) for test in created_tests]
            bulk_create_test_set_associations(
                db=db,
                test_ids=test_ids,
                test_set_id=test_set_id,
                organization_id=organization_id,
                user_id=user_id,
            )

        # Transaction commit/rollback is handled by the session context manager
        return created_tests

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to create tests: {error_msg}", exc_info=True)

        # Provide more specific error messages for common UUID issues
        if "invalid input syntax for type uuid" in error_msg.lower():
            if '""' in error_msg or "empty string" in error_msg.lower():
                error_msg = (
                    "Invalid UUID format: Empty string provided where UUID expected. "
                    "Check assignee_id and owner_id fields."
                )
            else:
                error_msg = f"Invalid UUID format in test data: {error_msg}"

        raise Exception(f"Failed to create tests: {error_msg}")


def create_test_set_associations(
    db: Session, test_set_id: str, test_ids: List[str], organization_id: str, user_id: str
) -> Dict[str, Any]:
    """
    Associate multiple tests with a test set, handling transactions and business logic.

    Args:
        db: Database session
        test_set_id: ID of the test set to associate with
        test_ids: List of test IDs to associate
        organization_id: Organization ID for the associations
        user_id: User ID creating the associations

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation was successful
        - total_tests: Total number of test IDs provided
        - message: Detailed message about the operation result
        - metadata: Dictionary containing detailed information about the operation
    """
    from rhesis.backend.app.models import TestSet

    # Transaction management is handled by the session context manager

    try:
        # Verify test set exists AND belongs to organization (SECURITY CRITICAL)
        from uuid import UUID

        test_set = (
            db.query(TestSet)
            .filter(TestSet.id == test_set_id, TestSet.organization_id == UUID(organization_id))
            .first()
        )
        if not test_set:
            return {
                "success": False,
                "total_tests": 0,
                "message": f"Test set with ID {test_set_id} not found or not accessible",
                "metadata": {
                    "new_associations": 0,
                    "existing_associations": 0,
                    "invalid_associations": 0,
                    "existing_test_ids": [],
                    "invalid_test_ids": [],
                },
            }

        # Create associations in bulk
        result = bulk_create_test_set_associations(
            db=db,
            test_ids=test_ids,
            test_set_id=test_set_id,
            organization_id=organization_id,
            user_id=user_id,
        )

        # Update test set attributes if any new associations were created
        if result.get("metadata", {}).get("new_associations", 0) > 0:
            from rhesis.backend.app.services.test_set import update_test_set_attributes

            update_test_set_attributes(db=db, test_set_id=test_set_id)

        # Transaction commit/rollback is handled by the session context manager

        return result

    except IntegrityError as e:
        return {
            "success": False,
            "total_tests": 0,
            "message": f"One or more tests are already associated with this test set: {str(e)}",
            "metadata": {
                "new_associations": 0,
                "existing_associations": 0,
                "invalid_associations": 0,
                "existing_test_ids": [],
                "invalid_test_ids": [],
            },
        }
    except Exception as e:
        return {
            "success": False,
            "total_tests": 0,
            "message": f"An error occurred while associating tests: {str(e)}",
            "metadata": {
                "new_associations": 0,
                "existing_associations": 0,
                "invalid_associations": 0,
                "existing_test_ids": [],
                "invalid_test_ids": [],
            },
        }


def remove_test_set_associations(
    db: Session, test_set_id: str, test_ids: List[str], organization_id: str, user_id: str
) -> Dict[str, Any]:
    """
    Remove associations between tests and a test set.

    Args:
        db: Database session
        test_set_id: ID of the test set to remove associations from
        test_ids: List of test IDs to disassociate
        organization_id: Organization ID for the associations
        user_id: User ID performing the disassociation

    Returns:
        Dict containing:
        - success: Boolean indicating if the operation was successful
        - total_tests: Total number of test IDs provided
        - removed_associations: Number of associations removed
        - message: Detailed message about the operation result
    """
    from rhesis.backend.app.models import TestSet

    # Transaction management is handled by the session context manager

    try:
        # Verify test set exists AND belongs to organization (SECURITY CRITICAL)
        from uuid import UUID

        test_set = (
            db.query(TestSet)
            .filter(TestSet.id == test_set_id, TestSet.organization_id == UUID(organization_id))
            .first()
        )
        if not test_set:
            return {
                "success": False,
                "total_tests": 0,
                "removed_associations": 0,
                "message": f"Test set with ID {test_set_id} not found or not accessible",
            }

        # Check if any of the provided test IDs are actually associated with the test set
        existing_associations = db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_set_id == test_set_id,
                test_test_set_association.c.test_id.in_(test_ids),
                test_test_set_association.c.organization_id == organization_id,
            )
        ).fetchall()

        if not existing_associations:
            return {
                "success": False,
                "total_tests": len(test_ids),
                "removed_associations": 0,
                "message": "None of the provided test IDs are associated with this test set",
            }

        # Delete associations
        result = db.execute(
            test_test_set_association.delete().where(
                test_test_set_association.c.test_set_id == test_set_id,
                test_test_set_association.c.test_id.in_(test_ids),
                test_test_set_association.c.organization_id == organization_id,
            )
        )

        removed_count = result.rowcount

        # Build detailed message
        message = f"Successfully removed {removed_count} test associations"

        # Update test set attributes if any associations were removed
        if removed_count > 0:
            from rhesis.backend.app.services.test_set import update_test_set_attributes

            update_test_set_attributes(db=db, test_set_id=test_set_id)

        # Transaction commit/rollback is handled by the session context manager

        return {
            "success": True,
            "total_tests": len(test_ids),
            "removed_associations": removed_count,
            "message": message,
        }

    except Exception as e:
        return {
            "success": False,
            "total_tests": len(test_ids),
            "removed_associations": 0,
            "message": f"An error occurred while removing test associations: {str(e)}",
        }

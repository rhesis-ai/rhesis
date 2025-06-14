import json
import random
import uuid
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import (
    EntityType,
    ERROR_BULK_CREATE_FAILED,
    ERROR_INVALID_UUID,
    ERROR_TEST_SET_NOT_FOUND,
)
from rhesis.backend.app.database import maintain_tenant_context
from rhesis.backend.app.models import Prompt, TestSet
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.stats import get_entity_stats, get_related_stats
from rhesis.backend.app.services.test import bulk_create_test_set_associations, bulk_create_tests
from rhesis.backend.app.utils.crud_utils import get_or_create_status, get_or_create_type_lookup
from rhesis.backend.app.utils.uuid_utils import (
    ensure_owner_id,
    validate_uuid_list,
    validate_uuid_parameters,
)
from rhesis.backend.logging import logger


def get_test_set(db: Session, test_set_id: uuid.UUID):
    return (
        db.query(TestSet)
        .filter(TestSet.id == test_set_id)
        .options(
            joinedload(TestSet.prompts).joinedload(Prompt.demographic),
            joinedload(TestSet.prompts).joinedload(Prompt.category),
            joinedload(TestSet.prompts).joinedload(Prompt.attack_category),
            joinedload(TestSet.prompts).joinedload(Prompt.topic),
            joinedload(TestSet.prompts).joinedload(Prompt.behavior),
            joinedload(TestSet.prompts).joinedload(Prompt.source),
            joinedload(TestSet.prompts).joinedload(Prompt.status),
            joinedload(TestSet.prompts).joinedload(Prompt.user),
        )
        .first()
    )


def load_defaults():
    """Load default values from bulk_defaults.json"""
    defaults_path = Path(__file__).parent / "bulk_defaults.json"
    with open(defaults_path) as f:
        return json.load(f)


def generate_test_set_attributes(
    db: Session, test_set: models.TestSet, defaults: Dict[str, Any], license_type: models.TypeLookup
) -> Dict[str, Any]:
    """
    Generate or update test set attributes based on its associated tests and prompts.

    Args:
        db: Database session
        test_set: The test set to generate attributes for
        defaults: Default values from bulk_defaults.json
        license_type: The license type for the test set

    Returns:
        Dict containing the complete attributes structure
    """
    # Get all unique IDs and names for each dimension
    topics = list(set(str(test.topic_id) for test in test_set.tests))
    behaviors = list(set(str(test.behavior_id) for test in test_set.tests))
    categories = list(set(str(test.category_id) for test in test_set.tests))

    # Get all unique names for metadata
    topic_names = list(set(test.topic.name for test in test_set.tests))
    behavior_names = list(set(test.behavior.name for test in test_set.tests))
    category_names = list(set(test.category.name for test in test_set.tests))

    # Get a random prompt's content for the sample (now through tests)
    sample = None
    if test_set.tests:
        # Filter tests that have prompts with content
        tests_with_prompts = [test for test in test_set.tests if test.prompt and test.prompt.content]
        if tests_with_prompts:
            sample = random.choice(tests_with_prompts).prompt.content

    # Count unique prompts (in case multiple tests reference the same prompt)
    unique_prompt_ids = set(str(test.prompt_id) for test in test_set.tests if test.prompt_id)
    total_prompts = len(unique_prompt_ids)

    return {
        "topics": topics,
        "behaviors": behaviors,
        "categories": categories,
        "metadata": {
            "sample": sample,
            "topics": topic_names,
            "behaviors": behavior_names,
            "categories": category_names,
            "license_type": license_type.type_value,
            "total_prompts": total_prompts,
            "total_tests": len(test_set.tests),
        },
    }


def bulk_create_test_set(
    db: Session,
    test_set_data: Dict[str, Any] | schemas.TestSetBulkCreate,
    organization_id: str,
    user_id: str,
) -> models.TestSet:
    """Create a test set with its associated tests in a single operation."""
    defaults = load_defaults()

    # Validate input UUIDs
    validation_error = validate_uuid_parameters(organization_id, user_id)
    if validation_error:
        raise Exception(ERROR_BULK_CREATE_FAILED.format(entity="test set", error=validation_error))

    try:
        with maintain_tenant_context(db):
            # Convert dictionary to schema if needed
            if isinstance(test_set_data, dict):
                test_set_data = schemas.TestSetBulkCreate(**test_set_data)

            # Get or create required relationships
            test_set_status = get_or_create_status(
                db=db,
                name=defaults["test_set"]["status"],
                entity_type=EntityType.GENERAL,
            )

            license_type = get_or_create_type_lookup(
                db=db,
                type_name="LicenseType",
                type_value=defaults["test_set"]["license_type"],
            )

            # Create test set with minimal attributes
            test_set = models.TestSet(
                name=test_set_data.name,
                description=test_set_data.description,
                short_description=test_set_data.short_description,
                status_id=test_set_status.id,
                license_type_id=license_type.id,
                user_id=user_id,
                organization_id=organization_id,
                owner_id=ensure_owner_id(getattr(test_set_data, 'owner_id', None), user_id),
                assignee_id=getattr(test_set_data, 'assignee_id', None),  # Keep as None if not provided
                priority=getattr(test_set_data, 'priority', None) or defaults["test_set"]["priority"],
                visibility=defaults["test_set"]["visibility"],
                attributes={},  # Will be updated after tests are created
            )

            db.add(test_set)
            db.flush()  # Get the test set ID

            # Create tests and associate with test set
            bulk_create_tests(
                db=db,
                tests_data=test_set_data.tests,
                organization_id=organization_id,
                user_id=user_id,
                test_set_id=str(test_set.id),
            )

            # Refresh test set to get all relationships
            db.refresh(test_set)

            # Generate and update attributes
            test_set.attributes = generate_test_set_attributes(
                db=db, test_set=test_set, defaults=defaults, license_type=license_type
            )

            # Commit the entire transaction
            db.commit()
            return test_set

    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to create test set: {str(e)}")


def get_test_set_stats(
    db: Session, current_user_organization_id: str | None, top: int | None = None, months: int = 6
) -> Dict:
    """
    Get comprehensive statistics about test sets.
    """
    return get_entity_stats(
        db=db,
        entity_model=models.TestSet,
        organization_id=current_user_organization_id,
        top=top,
        months=months,
    )


def get_test_set_test_stats(
    db: Session,
    test_set_id: str | None,
    current_user_organization_id: str | None,
    top: int | None = None,
    months: int = 6,
) -> Dict:
    """
    Get statistics about tests, optionally filtered by a specific test set.

    Args:
        db: Database session
        test_set_id: Optional ID of a specific test set to filter by
        current_user_organization_id: Optional organization ID for filtering
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
    """

    return get_related_stats(
        db=db,
        entity_model=models.TestSet,
        entity_id=test_set_id,
        related_model=models.Test,
        relationship_attr="tests",
        organization_id=current_user_organization_id,
        top=top,
        months=months,
        category_columns=["priority"],  # Only priority is treated as a category field
    )


def create_test_set_associations(
    db: Session, test_set_id: str, test_ids: List[str], organization_id: str, user_id: str
) -> Dict[str, Any]:
    """Associate multiple tests with a test set."""
    logger.info("Starting create_test_set_associations")
    logger.info(f"Input test_set_id: {test_set_id}")
    logger.info(f"Input test_ids: {test_ids}")

    # Validate input UUIDs
    validation_error = validate_uuid_parameters(test_set_id, organization_id, user_id)
    if validation_error:
        error_response = {
            "success": False,
            "total_tests": len(test_ids),
            "message": ERROR_INVALID_UUID.format(error=validation_error),
        }
        logger.info(f"UUID validation failed, returning: {error_response}")
        return error_response

    # Validate test IDs list
    test_ids_validation_error = validate_uuid_list(test_ids)
    if test_ids_validation_error:
        error_response = {
            "success": False,
            "total_tests": len(test_ids),
            "message": ERROR_INVALID_UUID.format(error=test_ids_validation_error),
        }
        logger.info(f"Test IDs validation failed, returning: {error_response}")
        return error_response

    try:
        with maintain_tenant_context(db):
            # Validate test set exists
            test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
            if not test_set:
                error_response = {
                    "success": False,
                    "total_tests": 0,
                    "message": ERROR_TEST_SET_NOT_FOUND.format(test_set_id=test_set_id),
                }
                logger.info(f"Test set not found, returning: {error_response}")
                return error_response

            logger.info("Test set found, calling bulk_create_test_set_associations")
            # Create associations and get result
            bulk_result = bulk_create_test_set_associations(
                db=db,
                test_ids=test_ids,
                test_set_id=test_set_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            logger.info(f"Result from bulk_create_test_set_associations: {bulk_result}")

            # If any associations were created, update test set attributes
            if bulk_result["new_associations"] > 0:
                logger.info("New associations created, updating test set attributes")
                db.refresh(test_set)
                test_set.attributes = generate_test_set_attributes(
                    db=db,
                    test_set=test_set,
                    defaults=load_defaults(),
                    license_type=test_set.license_type,
                )
                db.commit()

            logger.info(f"Returning final result: {bulk_result}")
            return bulk_result

    except Exception as e:
        db.rollback()
        error_response = {
            "success": False,
            "total_tests": len(test_ids),
            "message": f"An error occurred while creating test set associations: {str(e)}",
        }
        logger.info(f"Exception occurred, returning: {error_response}")
        return error_response


def remove_test_set_associations(
    db: Session, test_set_id: str, test_ids: List[str], organization_id: str, user_id: str
) -> Dict[str, Any]:
    """Remove associations between tests and a test set."""
    # Validate input UUIDs
    validation_error = validate_uuid_parameters(test_set_id, organization_id, user_id)
    if validation_error:
        return {
            "success": False,
            "total_tests": len(test_ids),
            "removed_associations": 0,
            "message": ERROR_INVALID_UUID.format(error=validation_error),
        }

    # Validate test IDs list
    test_ids_validation_error = validate_uuid_list(test_ids)
    if test_ids_validation_error:
        return {
            "success": False,
            "total_tests": len(test_ids),
            "removed_associations": 0,
            "message": ERROR_INVALID_UUID.format(error=test_ids_validation_error),
        }

    try:
        with maintain_tenant_context(db):
            # Get test set and verify it exists
            test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
            if not test_set:
                return {
                    "success": False,
                    "total_tests": 0,
                    "removed_associations": 0,
                    "message": ERROR_TEST_SET_NOT_FOUND.format(test_set_id=test_set_id),
                }

            # Remove associations
            result = db.execute(
                test_test_set_association.delete().where(
                    test_test_set_association.c.test_set_id == test_set_id,
                    test_test_set_association.c.test_id.in_(test_ids),
                    test_test_set_association.c.organization_id == organization_id,
                )
            )

            removed_count = result.rowcount

            # Refresh test set to get updated relationships
            db.refresh(test_set)

            # Update attributes
            test_set.attributes = generate_test_set_attributes(
                db=db,
                test_set=test_set,
                defaults=load_defaults(),
                license_type=test_set.license_type,
            )

            db.commit()

            return {
                "success": True,
                "total_tests": len(test_ids),
                "removed_associations": removed_count,
                "message": f"Successfully removed {removed_count} test associations",
            }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "total_tests": len(test_ids),
            "removed_associations": 0,
            "message": f"Failed to remove test set associations: {str(e)}",
        }


def update_test_set_attributes(db: Session, test_set_id: str) -> None:
    """
    Regenerate and update the attributes for a test set based on its current associated tests.

    Args:
        db: Database session
        test_set_id: UUID string of the test set to update

    Raises:
        ValueError: If test set not found or invalid UUID
    """
    from uuid import UUID

    # Validate UUID
    try:
        test_set_uuid = UUID(test_set_id)
    except ValueError:
        raise ValueError(ERROR_INVALID_UUID.format(entity="test set", id=test_set_id))

    with maintain_tenant_context(db):
        # Get test set with relationships
        test_set = (
            db.query(models.TestSet)
            .options(joinedload(models.TestSet.tests))
            .filter(models.TestSet.id == test_set_uuid)
            .first()
        )

        if not test_set:
            raise ValueError(ERROR_TEST_SET_NOT_FOUND.format(id=test_set_id))

        # Get defaults and license type
        defaults = load_defaults()
        license_type = get_or_create_type_lookup(
            db=db, type_name="LicenseType", type_value=defaults["test_set"]["license_type"]
        )

        # Regenerate attributes
        test_set.attributes = generate_test_set_attributes(
            db=db, test_set=test_set, defaults=defaults, license_type=license_type
        )

        db.commit()


def execute_test_set_on_endpoint(
    db: Session,
    test_set_identifier: str,
    endpoint_id: uuid.UUID,
    current_user: models.User,
) -> Dict[str, Any]:
    """
    Execute a test set against an endpoint by creating a test configuration and submitting it for execution.
    
    Args:
        db: Database session
        test_set_identifier: Test set identifier (UUID, nano_id, or slug)
        endpoint_id: Endpoint UUID
        current_user: Current authenticated user
        
    Returns:
        Dict containing execution status and metadata
        
    Raises:
        ValueError: For validation errors
        PermissionError: For access control errors
        RuntimeError: For execution errors
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app import schemas
    from rhesis.backend.tasks import task_launcher
    
    logger.info(
        f"Starting test set execution for identifier: {test_set_identifier} "
        f"and endpoint: {endpoint_id}, user: {current_user.id}"
    )

    # Validate input parameters
    if not test_set_identifier:
        raise ValueError("test_set_identifier is required")
    if not endpoint_id:
        raise ValueError("endpoint_id is required")

    with maintain_tenant_context(db):
        # Resolve test set
        logger.debug(f"Resolving test set with identifier: {test_set_identifier}")
        db_test_set = crud.resolve_test_set(test_set_identifier, db)
        if db_test_set is None:
            raise ValueError(f"Test Set not found with identifier: {test_set_identifier}")
        logger.info(f"Successfully resolved test set: {db_test_set.name} (ID: {db_test_set.id})")

        # Verify endpoint exists
        logger.debug(f"Verifying endpoint exists: {endpoint_id}")
        db_endpoint = crud.get_endpoint(db, endpoint_id=endpoint_id)
        if not db_endpoint:
            raise ValueError(f"Endpoint not found: {endpoint_id}")
        logger.info(f"Successfully verified endpoint: {db_endpoint.name} (ID: {db_endpoint.id})")

        # Check user access permissions
        _validate_user_access(current_user, db_test_set, db_endpoint)

        # Create test configuration
        test_config_id = _create_test_configuration(
            db, endpoint_id, db_test_set.id, current_user
        )

        # Submit for execution
        task_result = _submit_test_configuration_for_execution(test_config_id, current_user)

        # Return success response
        response_data = {
            "status": "submitted",
            "message": f"Test set execution started for {db_test_set.name}",
            "test_set_id": str(db_test_set.id),
            "test_set_name": db_test_set.name,
            "endpoint_id": str(endpoint_id),
            "endpoint_name": db_endpoint.name,
            "test_configuration_id": test_config_id,
            "task_id": task_result.id,
        }
        logger.info(f"Successfully initiated test set execution: {response_data}")
        return response_data


def _validate_user_access(
    current_user: models.User, 
    db_test_set: models.TestSet, 
    db_endpoint: models.Endpoint
) -> None:
    """Validate user has access to both test set and endpoint."""
    # Check if user has access to the test set
    logger.debug(
        f"Checking user access to test set: user_org={current_user.organization_id}, "
        f"test_set_org={db_test_set.organization_id}"
    )
    if str(current_user.organization_id) != str(db_test_set.organization_id):
        logger.error(
            f"User {current_user.id} from org {current_user.organization_id} "
            f"cannot access test set {db_test_set.id} from org {db_test_set.organization_id}"
        )
        raise PermissionError("Access denied: test set belongs to different organization")

    # Check if user has access to the endpoint
    logger.debug(
        f"Checking user access to endpoint: user_org={current_user.organization_id}, "
        f"endpoint_org={db_endpoint.organization_id}"
    )
    if str(current_user.organization_id) != str(db_endpoint.organization_id):
        logger.error(
            f"User {current_user.id} from org {current_user.organization_id} "
            f"cannot access endpoint {db_endpoint.id} from org {db_endpoint.organization_id}"
        )
        raise PermissionError("Access denied: endpoint belongs to different organization")


def _create_test_configuration(
    db: Session, 
    endpoint_id: uuid.UUID, 
    test_set_id: uuid.UUID, 
    current_user: models.User
) -> str:
    """Create test configuration and return its ID as string."""
    from rhesis.backend.app import crud, schemas
    
    logger.debug(
        f"Creating test configuration for test_set_id={test_set_id}, "
        f"endpoint_id={endpoint_id}, user_id={current_user.id}"
    )
    
    test_config = schemas.TestConfigurationCreate(
        endpoint_id=endpoint_id,
        test_set_id=test_set_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    logger.debug(f"Test configuration schema created: {test_config}")
    
    # Create the test configuration
    db_test_config = crud.create_test_configuration(db=db, test_configuration=test_config)
    print(f"I got db_test_config: {db_test_config}")
    # Access the ID immediately while we're still in the same transaction context
    # This avoids any potential session expiration or RLS context issues
    test_config_id = str(db_test_config.id)
    logger.info(f"Created test configuration with ID: {test_config_id}")
    
    # Return just the ID string instead of trying to access the object later
    return test_config_id


def _submit_test_configuration_for_execution(test_config_id: str, current_user: models.User):
    """Submit test configuration for background execution."""
    from rhesis.backend.tasks.test_configuration import execute_test_configuration
    from rhesis.backend.tasks import task_launcher
    
    logger.debug(f"Submitting test configuration for execution: test_configuration_id={test_config_id}")
    
    result = task_launcher(
        execute_test_configuration,
        test_config_id,
        current_user=current_user
    )
    
    logger.info(f"Test configuration execution submitted with task ID: {result.id}")
    return result

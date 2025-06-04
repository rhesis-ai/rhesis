import json
import random
import uuid
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.database import maintain_tenant_context
from rhesis.backend.app.models import Prompt, TestSet
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.stats import get_entity_stats, get_related_stats
from rhesis.backend.app.services.test import bulk_create_test_set_associations, bulk_create_tests
from rhesis.backend.app.utils.crud_utils import get_or_create_status, get_or_create_type_lookup


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

    try:
        with maintain_tenant_context(db):
            # Convert dictionary to schema if needed
            if isinstance(test_set_data, dict):
                test_set_data = schemas.TestSetBulkCreate(**test_set_data)

            # Get or create required relationships
            test_set_status = get_or_create_status(
                db=db,
                name=defaults["test_set"]["status"],
                entity_type="General",
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
    print("[DEBUG-SERVICE] Starting create_test_set_associations")
    print(f"[DEBUG-SERVICE] Input test_set_id: {test_set_id}")
    print(f"[DEBUG-SERVICE] Input test_ids: {test_ids}")

    try:
        with maintain_tenant_context(db):
            # Validate test set exists
            test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
            if not test_set:
                error_response = {
                    "success": False,
                    "total_tests": 0,
                    "message": f"Test set with ID {test_set_id} not found",
                }
                print(f"[DEBUG-SERVICE] Test set not found, returning: {error_response}")
                return error_response

            print("[DEBUG-SERVICE] Test set found, calling bulk_create_test_set_associations")
            # Create associations and get result
            bulk_result = bulk_create_test_set_associations(
                db=db,
                test_ids=test_ids,
                test_set_id=test_set_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            print(f"[DEBUG-SERVICE] Result from bulk_create_test_set_associations: {bulk_result}")

            # If any associations were created, update test set attributes
            if bulk_result["new_associations"] > 0:
                print("[DEBUG-SERVICE] New associations created, updating test set attributes")
                db.refresh(test_set)
                test_set.attributes = generate_test_set_attributes(
                    db=db,
                    test_set=test_set,
                    defaults=load_defaults(),
                    license_type=test_set.license_type,
                )
                db.commit()

            print(f"[DEBUG-SERVICE] Returning final result: {bulk_result}")
            return bulk_result

    except Exception as e:
        db.rollback()
        error_response = {
            "success": False,
            "total_tests": len(test_ids),
            "message": f"An error occurred while creating test set associations: {str(e)}",
        }
        print(f"[DEBUG-SERVICE] Exception occurred, returning: {error_response}")
        return error_response


def remove_test_set_associations(
    db: Session, test_set_id: str, test_ids: List[str], organization_id: str, user_id: str
) -> Dict[str, Any]:
    """Remove associations between tests and a test set."""
    try:
        with maintain_tenant_context(db):
            # Get test set and verify it exists
            test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
            if not test_set:
                return {
                    "success": False,
                    "total_tests": 0,
                    "removed_associations": 0,
                    "message": f"Test set with ID {test_set_id} not found",
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
    Update test set attributes after tests are added or removed.
    
    Args:
        db: Database session
        test_set_id: ID of the test set to update
    """
    test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
    if test_set:
        defaults = load_defaults()
        test_set.attributes = generate_test_set_attributes(
            db=db,
            test_set=test_set,
            defaults=defaults,
            license_type=test_set.license_type,
        )
        db.flush()

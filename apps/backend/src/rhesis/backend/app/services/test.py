import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.database import maintain_tenant_context
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.stats import get_entity_stats
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_entity,
    get_or_create_status,
    get_or_create_type_lookup,
)


def get_test_stats(
    db: Session,
    current_user_organization_id: str | None,
    top: int | None = None,
    months: int = 6,
) -> Dict:
    """
    Get comprehensive statistics about tests.

    Args:
        db: Database session
        current_user_organization_id: Optional organization ID for filtering
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
    """
    return get_entity_stats(
        db=db,
        entity_model=models.Test,
        organization_id=current_user_organization_id,
        top=top,
        months=months,
    )


def load_defaults():
    """Load default values from bulk_defaults.json"""
    defaults_path = Path(__file__).parent / "bulk_defaults.json"
    with open(defaults_path) as f:
        return json.load(f)


def _validate_test_set(
    db: Session, test_set_id: str
) -> tuple[models.TestSet | None, Dict[str, Any] | None]:
    """Validate test set exists and return it or error response."""
    test_set = db.query(models.TestSet).filter(models.TestSet.id == test_set_id).first()
    if not test_set:
        return None, {
            "success": False,
            "total_tests": 0,
            "message": f"Test set with ID {test_set_id} not found",
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

    # Find existing tests
    existing_tests = db.query(models.Test).filter(models.Test.id.in_(test_ids)).all()
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
        plural = 's' if new_associations != 1 else ''
        return f"Successfully associated {new_associations} new test{plural}."

    # Case: All tests were missing
    if missing_count == total and new_associations == 0 and already_associated_count == 0:
        plural = 's' if missing_count != 1 else ''
        return f"No tests were associated. All {missing_count} test{plural} could not be found."

    # Case: All tests were already associated
    if already_associated_count == total and new_associations == 0 and missing_count == 0:
        plural = 's' if already_associated_count != 1 else ''
        return (f"No new tests were associated. All {already_associated_count} "
                f"test{plural} were already associated.")

    # Mixed cases
    parts = []

    if new_associations > 0:
        plural = 's' if new_associations != 1 else ''
        parts.append(f"Successfully associated {new_associations} new test{plural}")

    if already_associated_count > 0:
        verb = 's were' if already_associated_count != 1 else ' was'
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
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Bulk create associations between tests and a test set in batches.
    Handles validation of test IDs and existing associations.
    """
    # First validate the test set exists
    test_set, error_response = _validate_test_set(db, test_set_id)
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


def create_entity_with_status(
    db: Session,
    model: Any,
    name: str,
    defaults: Dict,
    entity_type: str,
    organization_id: str,
    user_id: str,
    **extra_fields,
) -> Any:
    """Helper to create an entity with a status"""
    status = get_or_create_status(
        db=db,
        name=defaults[entity_type.lower()]["status"],
        entity_type="General",
    )

    return get_or_create_entity(
        db=db,
        model=model,
        entity_data={
            "name": name,
            "organization_id": organization_id,
            "user_id": user_id,
            "status_id": status.id,
            **extra_fields,
        },
    )


def prepare_test_data(
    test_data: Dict[str, Any] | schemas.TestData, defaults: Dict
) -> Dict[str, Any]:
    """Convert and prepare test data for processing"""
    if hasattr(test_data, "model_dump"):
        return test_data.model_dump()
    return test_data.copy()


def create_prompt(
    db: Session, prompt_data: Dict, defaults: Dict, organization_id: str, user_id: str
) -> models.Prompt:
    """Create a prompt with its associated entities"""
    if hasattr(prompt_data, "model_dump"):
        prompt_data = prompt_data.model_dump()

    demographic = None
    if "demographic" in prompt_data and "dimension" in prompt_data:
        dimension = create_entity_with_status(
            db=db,
            model=models.Dimension,
            name=prompt_data.pop("dimension"),
            defaults=defaults,
            entity_type="Dimension",
            organization_id=organization_id,
            user_id=user_id,
        )

        demographic = create_entity_with_status(
            db=db,
            model=models.Demographic,
            name=prompt_data.pop("demographic"),
            defaults=defaults,
            entity_type="Demographic",
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
                entity_type="General",
            ).id,
            "language_code": prompt_data.get("language_code", defaults["prompt"]["language_code"]),
            "demographic_id": demographic.id if demographic else None,
            "expected_response": prompt_data.get("expected_response"),
        },
    )


def bulk_create_tests(
    db: Session,
    tests_data: List[Dict[str, Any] | schemas.TestData],
    organization_id: str,
    user_id: str,
    test_set_id: str | None = None,
) -> List[models.Test]:
    """Bulk create tests from a list of test data dictionaries or TestData objects."""
    created_tests = []
    defaults = load_defaults()

    try:
        with maintain_tenant_context(db):
            # Get or create required relationships
            test_type = get_or_create_type_lookup(
                db=db,
                type_name="TestType",
                type_value=defaults["test"]["test_type"],
            )

            test_status = get_or_create_status(
                db=db,
                name=defaults["test"]["status"],
                entity_type="Test",
            )

            for test_data in tests_data:
                test_data_dict = prepare_test_data(test_data, defaults)
                prompt_data = test_data_dict.pop("prompt", {})

                # Create prompt and related entities
                prompt = create_prompt(
                    db=db,
                    prompt_data=prompt_data,
                    defaults=defaults,
                    organization_id=organization_id,
                    user_id=user_id,
                )

                # Create topic, behavior, and category
                topic = create_entity_with_status(
                    db=db,
                    model=models.Topic,
                    name=test_data_dict.pop("topic"),
                    defaults=defaults,
                    entity_type="Topic",
                    organization_id=organization_id,
                    user_id=user_id,
                )

                behavior = create_entity_with_status(
                    db=db,
                    model=models.Behavior,
                    name=test_data_dict.pop("behavior"),
                    defaults=defaults,
                    entity_type="Behavior",
                    organization_id=organization_id,
                    user_id=user_id,
                )

                category = create_entity_with_status(
                    db=db,
                    model=models.Category,
                    name=test_data_dict.pop("category"),
                    defaults=defaults,
                    entity_type="Category",
                    organization_id=organization_id,
                    user_id=user_id,
                )

                # Create test
                test_params = {
                    "prompt_id": prompt.id,
                    "test_type_id": test_type.id,
                    "topic_id": topic.id,
                    "behavior_id": behavior.id,
                    "category_id": category.id,
                    "status_id": test_status.id
                    if not test_data_dict.get("status")
                    else get_or_create_status(
                        db=db,
                        name=test_data_dict.pop("status"),
                        entity_type="Test",
                    ).id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "priority": test_data_dict.pop("priority", defaults["test"]["priority"]),
                    "test_configuration": test_data_dict.pop(
                        "test_configuration", defaults["test"]["test_configuration"]
                    ),
                    "assignee_id": test_data_dict.pop("assignee_id", None),
                    "owner_id": test_data_dict.pop("owner_id", None),
                }

                test = models.Test(**test_params)
                db.add(test)
                created_tests.append(test)

            db.flush()

            if test_set_id:
                test_ids = [str(test.id) for test in created_tests]
                bulk_create_test_set_associations(
                    db=db,
                    test_ids=test_ids,
                    test_set_id=test_set_id,
                    organization_id=organization_id,
                    user_id=user_id,
                )

            db.commit()
            return created_tests

    except Exception as e:
        db.rollback()
        raise Exception(f"Failed to create tests: {str(e)}")


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

    # Check if there's an existing transaction and roll it back
    if db.in_transaction():
        db.rollback()

    try:
        with maintain_tenant_context(db):
            # Verify test set exists
            test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
            if not test_set:
                return {
                    "success": False,
                    "total_tests": 0,
                    "message": f"Test set with ID {test_set_id} not found",
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

            # Commit the transaction
            db.commit()

            return result

    except IntegrityError as e:
        db.rollback()
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
        db.rollback()
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

    # Check if there's an existing transaction and roll it back
    if db.in_transaction():
        db.rollback()

    try:
        with maintain_tenant_context(db):
            # Verify test set exists
            test_set = db.query(TestSet).filter(TestSet.id == test_set_id).first()
            if not test_set:
                return {
                    "success": False,
                    "total_tests": 0,
                    "removed_associations": 0,
                    "message": f"Test set with ID {test_set_id} not found",
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

            # Commit the transaction
            db.commit()

            return {
                "success": True,
                "total_tests": len(test_ids),
                "removed_associations": removed_count,
                "message": message,
            }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "total_tests": len(test_ids),
            "removed_associations": 0,
            "message": f"An error occurred while removing test associations: {str(e)}",
        }

"""CRUD operations for tests.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the test-set functions, and per-entity modules like this one take over as the code around
them is touched -- see ``apps/backend/AGENTS.md``'s crud-layout rule.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.crud_utils import (
    bulk_delete_by_ids,
    create_item,
    get_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.hidden_rows import exclude_metric_owned
from rhesis.backend.app.utils.query_utils import include


def get_test(
    db: Session, test_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Test]:
    """Get test."""
    return get_item(db, models.Test, test_id, organization_id, user_id)


# Every many-to-one relationship TestDetail serializes -- see schemas/test.py.
# parent/source/organization/project are unused and intentionally excluded.
_TEST_RELATED_FIELDS = (
    include(models.Test.prompt),
    include(models.Test.test_type),
    include(models.Test.user),
    include(models.Test.assignee),
    include(models.Test.owner),
    include(models.Test.topic),
    include(models.Test.requirement),
    include(models.Test.category),
    include(models.Test.status),
)


def get_test_detail(
    db: Session, test_id: uuid.UUID, organization_id: str = None, user_id: str = None
) -> Optional[models.Test]:
    """Get test with all relationships loaded using optimized approach."""
    return get_item_detail(
        db, models.Test, test_id, organization_id, user_id, related_fields=_TEST_RELATED_FIELDS
    )


def get_tests(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str = None,
    user_id: str = None,
) -> List[models.Test]:
    """Get tests, minus the Explorer-owned ones (those belong to the /explorer API)."""
    # NOTE: No secondary_sort_by: Test.content sorting is a slow correlated subquery
    return get_items_detail(
        db,
        models.Test,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_TEST_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
        exclude_explorer_rows=True,
        # Metric tuning cases are reachable only through their metric. The route
        # pairs this with the same filter on its X-Total-Count.
        extra_filter=exclude_metric_owned(models.Test),
    )


def create_test(
    db: Session, test: schemas.TestCreate, organization_id: str = None, user_id: str = None
) -> models.Test:
    """Create test."""
    return create_item(db, models.Test, test, organization_id, user_id)


def update_test(
    db: Session,
    test_id: uuid.UUID,
    test: Dict[str, Any],
    organization_id: str = None,
    user_id: str = None,
) -> Optional[models.Test]:
    """Update test and refresh parent test set attributes when metadata changes.

    ``test`` must be the resolved update payload (e.g. from
    ``resolve_test_entity_names``), not the raw API schema.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    metadata_fields = {
        "requirement",
        "requirement_id",
        "topic",
        "topic_id",
        "category",
        "category_id",
        "test_type",
        "test_type_id",
    }
    should_refresh_attributes = bool(metadata_fields & set(test.keys()))

    db_test = update_item(db, models.Test, test_id, test, organization_id, user_id)
    if db_test is None:
        return None

    if should_refresh_attributes:
        affected_test_set_ids = (
            db.execute(
                select(test_test_set_association.c.test_set_id).where(
                    test_test_set_association.c.test_id == test_id,
                    test_test_set_association.c.organization_id == organization_id,
                )
            )
            .scalars()
            .all()
        )

        for test_set_id in affected_test_set_ids:
            update_test_set_attributes(
                db=db,
                test_set_id=str(test_set_id),
                organization_id=organization_id,
                user_id=user_id,
            )

    return db_test


def delete_test(
    db: Session, test_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.Test]:
    """
    Soft delete a test and update any associated test sets' attributes.

    The test is marked as deleted but remains in the database to preserve
    referential integrity with test runs, results, and other related data.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    # Get the test to be deleted
    db_test = get_item(db, models.Test, test_id, organization_id, user_id)
    if db_test is None:
        return None

    # Get all test sets that contain this test before deletion
    test_set_ids = db.execute(
        test_test_set_association.select().where(test_test_set_association.c.test_id == test_id)
    ).fetchall()

    affected_test_set_ids = [row.test_set_id for row in test_set_ids]

    # Soft delete the test (preserves referential integrity)
    db_test.soft_delete()
    db.commit()
    db.refresh(db_test)

    # Update attributes for all affected test sets
    for test_set_id in affected_test_set_ids:
        update_test_set_attributes(
            db=db,
            test_set_id=str(test_set_id),
            organization_id=organization_id,
            user_id=user_id,
        )

    # Return the soft-deleted test
    return db_test


def bulk_delete_tests(
    db: Session,
    test_ids: List[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """
    Soft delete multiple tests in one transaction and recompute test-set
    attributes once per distinct affected test set (not once per deleted test).

    Deleting the same 25 tests one at a time (25 DELETE /tests/{id} requests)
    recomputes -- and re-UPDATEs -- a shared test set's attributes up to 25
    times, and those concurrent UPDATEs to the same row serialize at the
    database. Resolving the affected test sets across the whole batch up
    front and recomputing each exactly once avoids both problems.
    """
    from rhesis.backend.app.services.test_set import update_test_set_attributes

    if not test_ids:
        return {"deleted_ids": [], "not_found_ids": []}

    def _recompute_affected_test_sets(deleted_ids: List[uuid.UUID]) -> None:
        rows = db.execute(
            test_test_set_association.select().where(
                test_test_set_association.c.test_id.in_(deleted_ids),
                test_test_set_association.c.organization_id == organization_id,
            )
        ).fetchall()
        affected_test_set_ids = {row.test_set_id for row in rows}
        for test_set_id in affected_test_set_ids:
            update_test_set_attributes(
                db=db,
                test_set_id=str(test_set_id),
                organization_id=organization_id,
                user_id=user_id,
            )

    return bulk_delete_by_ids(
        db,
        models.Test,
        test_ids,
        organization_id=organization_id,
        user_id=user_id,
        on_deleted=_recompute_affected_test_sets,
    )

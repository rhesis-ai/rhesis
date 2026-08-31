"""CRUD operations for test results.

``_TEST_RESULT_RELATED_FIELDS`` is what ``TestResultDetail`` serializes -- the test run, the
test, and the test's prompt and requirement. All many-to-one, so eager-loading them in one
query costs nothing; without them a results list issues four queries per row.
"""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

_TEST_RESULT_RELATED_FIELDS = (
    include(models.TestResult.test_run),
    include(models.TestResult.test),
    include(models.TestResult.test, models.Test.prompt),
    include(models.TestResult.test, models.Test.requirement),
)


def get_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestResult]:
    """Get test_result with relationships (tags, test, test_run) eagerly loaded."""
    return get_item_detail(
        db,
        models.TestResult,
        test_result_id,
        organization_id=organization_id,
        user_id=user_id,
        related_fields=_TEST_RESULT_RELATED_FIELDS,
    )


def get_test_results(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.TestResult]:
    """Get test_results with relationships (tags, test, test_run) eagerly loaded."""
    return (
        QueryBuilder(db, models.TestResult)
        .with_related(*_TEST_RESULT_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_test_result(
    db: Session,
    test_result: schemas.TestResultCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.TestResult:
    """Create test_result."""
    return create_item(db, models.TestResult, test_result, organization_id, user_id)


def update_test_result(
    db: Session,
    test_result_id: uuid.UUID,
    test_result: schemas.TestResultUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestResult]:
    """Update test_result."""
    return update_item(db, models.TestResult, test_result_id, test_result, organization_id, user_id)


def delete_test_result(
    db: Session, test_result_id: uuid.UUID, organization_id: str, user_id: str
) -> Optional[models.TestResult]:
    return delete_item(
        db, models.TestResult, test_result_id, organization_id=organization_id, user_id=user_id
    )

"""CRUD operations for test configurations."""

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
from rhesis.backend.app.utils.query_utils import QueryBuilder


def get_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    return get_item_detail(
        db,
        models.TestConfiguration,
        test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )


def get_test_configurations(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.TestConfiguration]:
    return (
        QueryBuilder(db, models.TestConfiguration)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )


def create_test_configuration(
    db: Session,
    test_configuration: schemas.TestConfigurationCreate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> models.TestConfiguration:
    return create_item(
        db,
        models.TestConfiguration,
        test_configuration,
        organization_id=organization_id,
        user_id=user_id,
    )


def update_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    test_configuration: schemas.TestConfigurationUpdate,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    """Update test_configuration."""
    return update_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        test_configuration,
        organization_id,
        user_id,
    )


def delete_test_configuration(
    db: Session,
    test_configuration_id: uuid.UUID,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> Optional[models.TestConfiguration]:
    """Delete test_configuration."""
    return delete_item(
        db,
        models.TestConfiguration,
        test_configuration_id,
        organization_id=organization_id,
        user_id=user_id,
    )

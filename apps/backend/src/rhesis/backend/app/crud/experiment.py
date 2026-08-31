"""CRUD operations for experiments."""

from typing import List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.query_utils import QueryBuilder, include


def get_experiments(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> List[models.Experiment]:
    return (
        QueryBuilder(db, models.Experiment)
        .with_related(include(models.Experiment.project))
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_odata_filter(filter)
        .with_sorting(sort_by, sort_order)
        .with_pagination(skip, limit)
        .all()
    )

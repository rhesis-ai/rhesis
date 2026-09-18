"""CRUD operations for experiments."""

from __future__ import annotations

import uuid
from typing import Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.crud_utils import bulk_delete_by_ids
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


def _unbind_environments_for_experiments(
    db: Session,
    experiment_ids: list[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> None:
    """Unbind project environments pointing at any of the given experiments.

    Same pre-delete work the single-item delete route does per experiment,
    batched here so the bulk path doesn't regress the environment invariant.
    """
    from rhesis.backend.app.crud.project import get_project
    from rhesis.backend.app.services.experiment import (
        environments_pointing_at_experiment,
        unbind_environment,
    )

    rows = (
        QueryBuilder(db, models.Experiment)
        .with_organization_filter(organization_id)
        .with_visibility_filter(user_id)
        .with_custom_filter(lambda q: q.filter(models.Experiment.id.in_(experiment_ids)))
        .with_custom_filter(lambda q: q.filter(models.Experiment.owner_user_id == user_id))
        .all()
    )

    for experiment in rows:
        project = get_project(
            db,
            project_id=experiment.project_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if project is None:
            continue
        for env_name in environments_pointing_at_experiment(project, experiment.id):
            unbind_environment(db, project=project, environment_name=env_name)


def bulk_delete_experiments(
    db: Session,
    experiment_ids: list[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> Dict[str, List[str]]:
    """Soft delete multiple experiments in one transaction.

    Unbinds project environments first (matching single-delete behaviour),
    then delegates to the shared bulk helper with owner_user_id gating so
    only the creator may delete their own experiments.
    """
    _unbind_environments_for_experiments(db, experiment_ids, organization_id, user_id)

    return bulk_delete_by_ids(
        db,
        models.Experiment,
        experiment_ids,
        organization_id=organization_id,
        user_id=user_id,
        owner_attr="owner_user_id",
    )

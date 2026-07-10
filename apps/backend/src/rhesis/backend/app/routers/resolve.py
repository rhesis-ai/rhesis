"""Cross-project entity resolution endpoint.

When a user follows a shared link to an entity that belongs to a different
project than their currently active one, the auto-filter returns 404. This
endpoint lets the frontend discover the entity's actual project so it can
offer a "switch project" prompt instead of a confusing "Not Found" page.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import UnmappedClassError

from rhesis.backend.app import models
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_project_context, get_tenant_db_session
from rhesis.backend.app.models.base import Base
from rhesis.backend.app.models.user import User
from rhesis.backend.app.scope import bypass_tenant_filter

router = APIRouter(prefix="/resolve", tags=["resolve"])


def get_resolvable_entities() -> dict[str, type]:
    """Discover project-scoped models eligible for cross-project resolution.

    Mirrors the ``get_all_models()`` pattern in ``routers/recycle.py``: every
    model is found via SQLAlchemy's own class registry instead of a hand-kept
    list, so newly added project-scoped models are picked up automatically.
    Only models carrying both ``project_id`` and ``organization_id`` qualify.
    """
    entities: dict[str, type] = {}
    for mapper in Base.registry.mappers:
        try:
            model_class = mapper.class_
        except UnmappedClassError:
            continue
        if hasattr(model_class, "project_id") and hasattr(model_class, "organization_id"):
            entities[model_class.__tablename__] = model_class
    return entities


class ResolvedEntity(BaseModel):
    resolution: str
    entity_type: str
    entity_id: str
    project_id: str | None = None
    project_name: str | None = None


@router.get("", response_model=ResolvedEntity)
def resolve_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    project_id: str | None = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Resolve an entity across projects within the caller's organization.

    Returns one of three resolutions:
    - ``switchable``: entity is in a different project the caller can access
    - ``no_access``: entity exists but the caller lacks project membership
      (project details are withheld)
    - 404: entity does not exist, is deleted, or belongs to another org
    """
    model_cls = get_resolvable_entities().get(entity_type)
    if model_cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown entity type: {entity_type}",
        )

    organization_id = str(current_user.organization_id)
    user_id = str(current_user.id)

    with bypass_tenant_filter():
        entity = (
            db.query(model_cls)
            .filter(
                model_cls.id == entity_id,
                model_cls.organization_id == organization_id,
            )
            .first()
        )

    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if hasattr(entity, "deleted_at") and entity.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    entity_project_id = str(entity.project_id) if entity.project_id else None

    if entity_project_id is None or entity_project_id == (project_id or ""):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    with bypass_tenant_filter():
        membership = (
            db.query(models.ProjectMembership)
            .filter(
                models.ProjectMembership.user_id == user_id,
                models.ProjectMembership.project_id == entity_project_id,
                models.ProjectMembership.organization_id == organization_id,
            )
            .first()
        )

    if membership is None:
        return ResolvedEntity(
            resolution="no_access",
            entity_type=entity_type,
            entity_id=str(entity_id),
        )

    with bypass_tenant_filter():
        project = (
            db.query(models.Project)
            .filter(
                models.Project.id == entity_project_id,
                models.Project.organization_id == organization_id,
            )
            .first()
        )

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return ResolvedEntity(
        resolution="switchable",
        entity_type=entity_type,
        entity_id=str(entity_id),
        project_id=str(project.id),
        project_name=project.name,
    )

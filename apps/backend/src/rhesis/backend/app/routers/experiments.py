"""Experiment header CRUD + versions sub-resource.

Two routers, one mount: per-project list / create lives on
``/projects/{project_id}/experiments`` (in :mod:`parameters` to keep
all project-scoped surface together), and the singleton experiment
endpoints live here on ``/experiments/{experiment_id}``. The plan
calls these "header" endpoints because the version array is appended
through a sub-resource and visibility flips through ``PATCH``.

Visibility, project scoping, append idempotency, and label-bind
guards are all enforced by :mod:`rhesis.backend.app.services.experiment`
so this router stays thin: parse, dispatch, format.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.experiment import Experiment
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.parameters import (
    ExperimentDetail,
    ExperimentRead,
    ExperimentUpdate,
    ExperimentVersion,
    ExperimentVersionCreate,
    ParameterSchema,
)
from rhesis.backend.app.services.experiment import (
    append_version,
    assert_no_active_labels,
    find_version,
    get_visible_experiment,
    latest_version,
)

router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


def _coerce_schema(project) -> ParameterSchema:
    raw = project.parameters_schema
    if isinstance(raw, ParameterSchema):
        return raw
    if raw is None:
        return ParameterSchema()
    return ParameterSchema.model_validate(raw)


def _to_read(db_experiment: Experiment) -> ExperimentRead:
    """Compact list / single shape — omits the inline ``versions`` array."""
    last = latest_version(db_experiment)
    return ExperimentRead(
        id=db_experiment.id,
        name=db_experiment.name,
        description=db_experiment.description,
        visibility=db_experiment.visibility,  # type: ignore[arg-type]
        project_id=db_experiment.project_id,
        owner_user_id=db_experiment.owner_user_id,
        organization_id=db_experiment.organization_id,
        versions_count=len(db_experiment.versions or []),
        latest_version=last.version if last else None,
        created_at=db_experiment.created_at,
        updated_at=db_experiment.updated_at,
    )


def _to_detail(db_experiment: Experiment) -> ExperimentDetail:
    """Detail shape — inlines the ``versions`` array."""
    versions: list[ExperimentVersion] = [
        v if isinstance(v, ExperimentVersion) else ExperimentVersion.model_validate(v)
        for v in (db_experiment.versions or [])
    ]
    last = versions[-1] if versions else None
    return ExperimentDetail(
        id=db_experiment.id,
        name=db_experiment.name,
        description=db_experiment.description,
        visibility=db_experiment.visibility,  # type: ignore[arg-type]
        project_id=db_experiment.project_id,
        owner_user_id=db_experiment.owner_user_id,
        organization_id=db_experiment.organization_id,
        versions_count=len(versions),
        latest_version=last.version if last else None,
        created_at=db_experiment.created_at,
        updated_at=db_experiment.updated_at,
        versions=versions,
    )


@router.get("/{experiment_id}", response_model=ExperimentDetail)
def read_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentDetail:
    """Return one experiment with its full version history.

    Visibility 404 applies: requesters who can't see the experiment
    get the same 404 as a missing id, never a 403.
    """
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    return _to_detail(db_experiment)


@router.patch("/{experiment_id}", response_model=ExperimentDetail)
def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentDetail:
    """Update header fields. Visibility flips guard the label invariant.

    Specifically: unsharing (``visibility: 'shared' → 'private'``) is
    refused with 409 if any project label currently points at this
    experiment, because labels can only target shared experiments.
    The caller has to move the label first. Re-sharing a private
    experiment is unconditional (no labels can target it yet).
    """
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )

    data = payload.model_dump(exclude_unset=True)

    new_visibility = data.get("visibility")
    if (
        new_visibility is not None
        and new_visibility != db_experiment.visibility
        and db_experiment.visibility == "shared"
        and new_visibility == "private"
    ):
        project = crud.get_project(
            db,
            project_id=db_experiment.project_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if project is not None:
            assert_no_active_labels(
                project,
                db_experiment.id,
                action="unshare",
            )

    for key, value in data.items():
        setattr(db_experiment, key, value)
    db.add(db_experiment)
    db.flush()
    db.refresh(db_experiment)
    return _to_detail(db_experiment)


@router.delete("/{experiment_id}", response_model=ExperimentRead)
def delete_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentRead:
    """Soft-delete an experiment. Refused if any label still points at it.

    Same 409-then-move-the-label-first dance as ``PATCH visibility``;
    same rationale.
    """
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )

    project = crud.get_project(
        db,
        project_id=db_experiment.project_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if project is not None:
        assert_no_active_labels(project, db_experiment.id, action="delete")

    snapshot = _to_read(db_experiment)
    crud.delete_item(
        db,
        Experiment,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    return snapshot


# --------------------------------------------------------------------------- #
# Versions sub-resource                                                       #
# --------------------------------------------------------------------------- #


@router.post(
    "/{experiment_id}/versions",
    response_model=ExperimentVersion,
)
def create_experiment_version(
    experiment_id: uuid.UUID,
    payload: ExperimentVersionCreate,
    response: Response,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentVersion:
    """Append a new immutable version to ``experiment_id``.

    The values are validated against the project's *current* schema
    (so editors can't commit references to deleted slots), then the
    server hashes them, locks the experiment row, and either appends
    a new entry or returns the existing latest entry verbatim if the
    hash matches (idempotent on re-save).

    The HTTP status reflects whether a new entry was created: 201 for
    a fresh append, 200 for an idempotent no-op so callers can
    distinguish "your save was actually new" from "you double-clicked
    Save".
    """
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )

    project = crud.get_project(
        db,
        project_id=db_experiment.project_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    project_schema = _coerce_schema(project)

    try:
        result = append_version(
            db,
            db_experiment=db_experiment,
            project_schema=project_schema,
            raw_values=payload.values,
            message=payload.message,
            parent_version=payload.parent_version,
            created_by_user_id=current_user.id,
        )
    except ValueError as exc:
        # validate_values_against_schema raises ValueError on missing
        # required slots, type mismatches, and out-of-range enum
        # values. FastAPI surfaces these as 422 so the editor can
        # render them inline next to the offending field.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return result.version


@router.get(
    "/{experiment_id}/versions",
    response_model=list[ExperimentVersion],
)
def list_experiment_versions(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> list[ExperimentVersion]:
    """Return all versions for the experiment, oldest → newest."""
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    return [
        v if isinstance(v, ExperimentVersion) else ExperimentVersion.model_validate(v)
        for v in (db_experiment.versions or [])
    ]


@router.get(
    "/{experiment_id}/versions/{version}",
    response_model=ExperimentVersion,
)
def read_experiment_version(
    experiment_id: uuid.UUID,
    version: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentVersion:
    """Return one version by content hash; 404 if it doesn't exist."""
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    return find_version(db_experiment, version)


__all__ = ["router"]

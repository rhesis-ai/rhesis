"""Experiment header CRUD + versions sub-resource.

Two routers, one mount: per-project list / create lives on
``/projects/{project_id}/experiments`` (in :mod:`parameters` to keep
all project-scoped surface together), and the singleton experiment
endpoints live here on ``/experiments/{experiment_id}``. The plan
calls these "header" endpoints because the version array is appended
through a sub-resource and visibility flips through ``PATCH``.

Visibility, project scoping, append idempotency, and environment-bind
guards are all enforced by :mod:`rhesis.backend.app.services.experiment`
so this router stays thin: parse, dispatch, format.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from rhesis.backend.app.routers.base import RhesisRouter
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
)
from rhesis.backend.app.services.experiment import (
    append_version,
    assert_no_active_environments,
    coerce_schema,
    environments_pointing_at_experiment,
    find_version,
    get_visible_experiment,
    to_detail,
    to_read,
    unbind_environment,
)

router = RhesisRouter(
    prefix="/experiments",
    tags=["experiments"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="experiment",
)


@router.get("", response_model=list[ExperimentRead])
def list_experiments(
    response: Response,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> list[ExperimentRead]:
    """List all experiments visible to the requester across projects.

    Supports OData filtering on ``name``, ``description``,
    ``visibility``, and ``project/name``.  Private experiments
    belonging to other users are excluded.
    """
    organization_id, user_id = tenant_context
    rows = crud.get_experiments(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    visible = [
        r
        for r in rows
        if r.visibility != "private"
        or (user_id is not None and str(r.owner_user_id) == str(user_id))
    ]
    response.headers["X-Total-Count"] = str(len(visible))
    return [to_read(r) for r in visible]


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
    return to_detail(db_experiment)


@router.patch("/{experiment_id}", response_model=ExperimentDetail)
def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentDetail:
    """Update header fields. Visibility flips guard the environment invariant.

    Specifically: unsharing (``visibility: 'shared' → 'private'``) is
    refused with 409 if any project environment currently points at this
    experiment, because environments can only target shared experiments.
    The caller has to move the environment first. Re-sharing a private
    experiment is unconditional (no environments can target it yet).
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
            assert_no_active_environments(
                project,
                db_experiment.id,
                action="unshare",
            )

    for key, value in data.items():
        setattr(db_experiment, key, value)
    db.add(db_experiment)
    db.commit()
    db.refresh(db_experiment)
    return to_detail(db_experiment)


@router.delete("/{experiment_id}", response_model=ExperimentRead)
def delete_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentRead:
    """Soft-delete an experiment.

    Any project environments pointing at this experiment are
    automatically unbound before deletion.
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
        for env_name in environments_pointing_at_experiment(project, db_experiment.id):
            unbind_environment(db, project=project, environment_name=env_name)

    snapshot = to_read(db_experiment)
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
    project_schema = coerce_schema(project)

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
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
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
    """Return one version by version label or content hash; 404 if it doesn't exist."""
    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    return find_version(db_experiment, version)


@router.get(
    "/{experiment_id}/results",
    response_model=dict,
)
def get_experiment_results(
    experiment_id: uuid.UUID,
    group_by: str = Query("run", description="Group by 'run' or 'version'"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> dict:
    """Aggregate TestRun results by run or by version."""
    from fastapi.encoders import jsonable_encoder

    organization_id, user_id = tenant_context
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )

    runs = crud.get_test_runs(
        db,
        skip=0,
        limit=limit,
        experiment_id=str(experiment_id),
        organization_id=organization_id,
        user_id=user_id,
    )

    # Real per-run counts, aggregated from test_result.status. Avoids the
    # stale/incomplete ``attributes.passed_tests`` / ``failed_tests``
    # counters that get written during execution and don't reflect later
    # metric- or turn-override recalculations.
    from rhesis.backend.tasks.execution.result_processor import (
        get_test_statistics_for_runs,
    )

    run_stats = get_test_statistics_for_runs(
        db,
        [run.id for run in runs],
        organization_id=organization_id,
    )

    def _with_stats(run) -> dict:
        encoded = jsonable_encoder(run)
        encoded["stats"] = run_stats.get(
            str(run.id),
            {"total": 0, "passed": 0, "failed": 0, "errors": 0},
        )
        return encoded

    if group_by == "run":
        return {"items": [_with_stats(r) for r in runs]}

    # Version-grouped response with diffs
    version_groups: dict[str, dict] = {}
    for run in runs:
        v = (run.attributes or {}).get("parameter_version")
        if not v:
            continue
        if v not in version_groups:
            version_groups[v] = {
                "version": v,
                "runs": [],
                "total_tests": 0,
                "diff": {},
            }
        version_groups[v]["runs"].append(_with_stats(run))
        version_groups[v]["total_tests"] += run_stats.get(str(run.id), {}).get("total", 0)

    # Walk versions newest-first, compute diffs against parent
    versions_in_order = [
        v.version if isinstance(v, ExperimentVersion) else v.get("version")
        for v in (db_experiment.versions or [])
    ]

    items = []
    for v_id in reversed(versions_in_order):
        if v_id not in version_groups:
            continue
        v_entry = find_version(db_experiment, v_id)
        current_values = v_entry.values
        diff: dict[str, dict] = {}
        if v_entry.parent_version:
            try:
                parent = find_version(db_experiment, v_entry.parent_version)
                parent_values = parent.values
                all_keys = set(current_values) | set(parent_values)
                for k in all_keys:
                    cv = current_values.get(k)
                    pv = parent_values.get(k)
                    if cv != pv:
                        diff[k] = {
                            "before": jsonable_encoder(pv),
                            "after": jsonable_encoder(cv),
                        }
            except HTTPException:
                pass
        group_data = version_groups[v_id]
        group_data["diff"] = diff
        items.append(group_data)

    return {"items": items}


__all__ = ["router"]

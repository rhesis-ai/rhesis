"""Project-scoped parameter management endpoints.

This router carries the full surface that lives under
``/projects/{project_id}/parameters/...`` plus the per-project
experiments *list/create* endpoints. The singleton experiment
endpoints (`GET /experiments/{id}`, version sub-resource, …) live in
:mod:`rhesis.backend.app.routers.experiments` because they're not
project-scoped in the URL even though the data is.

Endpoints in this module:

- ``GET / PUT /projects/{id}/parameters/schema``
- ``GET /projects/{id}/parameters/environments``
- ``PUT / DELETE /projects/{id}/parameters/environments/{name}``
- ``GET /projects/{id}/parameters/resolve``
- ``GET / POST /projects/{id}/experiments``

Visibility, project-scoping, and the resolver invariants are
enforced by :mod:`rhesis.backend.app.services.experiment` so the
routes stay thin.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.experiment import Experiment as ExperimentModel
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.parameters import (
    ENVIRONMENT_NAME_MAX_LENGTH,
    ENVIRONMENT_NAME_PATTERN,
    EnvironmentBindRequest,
    EnvironmentPointer,
    EnvironmentRegisterRequest,
    ExperimentCreate,
    ExperimentRead,
    ParameterSchema,
    ProjectEnvironments,
    ResolveResponse,
)
from rhesis.backend.app.services import experiment as experiment_service
from rhesis.backend.app.services.experiment import (
    coerce_environments,
    coerce_schema,
    to_read,
)

router = APIRouter(
    prefix="/projects/{project_id}/parameters",
    tags=["parameters"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


# A second router for the per-project *experiments* collection. Mounted
# under the same project prefix but a different URL segment, so it
# carries its own tag for the OpenAPI grouping.
project_experiments_router = APIRouter(
    prefix="/projects/{project_id}/experiments",
    tags=["experiments"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _load_project(
    project_id: uuid.UUID,
    db: Session,
    organization_id: str,
    user_id: str,
):
    db_project = crud.get_project(
        db,
        project_id=project_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return db_project




# --------------------------------------------------------------------------- #
# Schema GET / PUT                                                            #
# --------------------------------------------------------------------------- #


@router.get("/schema", response_model=ParameterSchema)
def get_parameters_schema(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ParameterSchema:
    """Return the project's :class:`ParameterSchema`.

    Empty schemas serialize as ``{"fields": []}`` — the same default
    the column carries on insert, so a freshly created project is
    indistinguishable on the wire from one that has been deliberately
    cleared.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    return coerce_schema(project)


@router.put("/schema", response_model=ParameterSchema)
def put_parameters_schema(
    project_id: uuid.UUID,
    payload: ParameterSchema,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ParameterSchema:
    """Replace the project's :class:`ParameterSchema` atomically.

    Last-write-wins: concurrent edits clobber each other. An
    ``If-Match`` ETag is deferred to v2 (see plan). The whole schema
    goes in and out in one round-trip, which matches what the list
    editor produces on save and keeps the API surface minimal.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    project.parameters_schema = payload
    db.add(project)
    db.commit()
    db.refresh(project)
    return coerce_schema(project)


# --------------------------------------------------------------------------- #
# Environments (read all + bind/unbind one)                                   #
# --------------------------------------------------------------------------- #


@router.get("/environments", response_model=ProjectEnvironments)
def get_project_environments(
    project_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ProjectEnvironments:
    """Return every environment the project knows about.

    Bound entries carry an :class:`EnvironmentPointer`; registered-but-
    unbound entries (created via ``POST``) carry ``null``. Built-in
    names that have neither been bound nor registered are not in the
    response — the frontend overlays them client-side from
    :attr:`BuiltInEnvironment.ALL` so the UI keeps rendering
    ``default`` / ``development`` / ``staging`` / ``production`` rows
    even before any binding exists.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    return coerce_environments(project)


@router.post(
    "/environments",
    response_model=ProjectEnvironments,
    status_code=status.HTTP_201_CREATED,
)
def register_project_environment(
    project_id: uuid.UUID,
    payload: EnvironmentRegisterRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ProjectEnvironments:
    """Register a new custom environment name without binding an experiment.

    The new entry has a ``null`` pointer until the user promotes an
    experiment onto it via ``PUT /environments/{name}``. Refused with
    **409** when the name is already present (bound or unbound) or is
    one of the always-available well-known names; refused with **422**
    when the name shape doesn't match the route pattern.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    return experiment_service.register_environment(
        db,
        project=project,
        environment_name=payload.name,
    )


@router.put("/environments/{environment_name}", response_model=ProjectEnvironments)
def put_project_environment(
    project_id: uuid.UUID,
    environment_name: Annotated[
        str,
        Path(
            pattern=ENVIRONMENT_NAME_PATTERN,
            min_length=1,
            max_length=ENVIRONMENT_NAME_MAX_LENGTH,
            description=(
                "Project-unique environment name. Lowercase alphanumeric "
                "plus '.', '_', '-' (must start with an alphanumeric), "
                f"up to {ENVIRONMENT_NAME_MAX_LENGTH} chars."
            ),
        ),
    ],
    payload: EnvironmentBindRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ProjectEnvironments:
    """Bind or move ``environment_name`` to ``(experiment_id, version)``.

    The name itself is validated by FastAPI from the route's
    ``Path(pattern=..., min_length=..., max_length=...)`` constraint so
    bad shapes (uppercase, leading punctuation, whitespace, empty,
    over-long) fail fast with 422 before reaching the service layer.

    Refused with 409 when the experiment isn't ``shared`` — the
    "environments point only at shared experiments" invariant is enforced
    here, and protected from later violation by the no-active-environment
    rule on unsharing.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    pointer = EnvironmentPointer(
        experiment_id=payload.experiment_id,
        version=payload.version,
    )
    return experiment_service.bind_environment(
        db,
        project=project,
        environment_name=environment_name,
        pointer=pointer,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/environments/{environment_name}", response_model=ProjectEnvironments)
def delete_project_environment(
    project_id: uuid.UUID,
    environment_name: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ProjectEnvironments:
    """Unbind ``environment_name`` (idempotent — unknown names succeed).

    Intentionally not pattern-constrained: any value that has been
    successfully written by older revisions of this API (before the
    name-shape rule existed) must remain deletable so operators can
    clean up bad data without a manual SQL surgery.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    return experiment_service.unbind_environment(
        db,
        project=project,
        environment_name=environment_name,
    )


# --------------------------------------------------------------------------- #
# Resolver                                                                    #
# --------------------------------------------------------------------------- #


@router.get("/resolve", response_model=ResolveResponse)
def resolve(
    project_id: uuid.UUID,
    environment: str | None = Query(default=None),
    experiment_id: uuid.UUID | None = Query(default=None),
    version: str | None = Query(default=None),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ResolveResponse:
    """Single canonical resolver shared by SDK and run-snapshot path.

    See :func:`experiment_service.resolve_parameters` for the
    precedence and visibility rules.
    """
    organization_id, user_id = tenant_context
    project = _load_project(project_id, db, organization_id, user_id)
    return experiment_service.resolve_parameters(
        db,
        project=project,
        environment=environment,
        experiment_id=experiment_id,
        version=version,
        organization_id=organization_id,
        user_id=user_id,
    )


# --------------------------------------------------------------------------- #
# Per-project experiments collection                                          #
# --------------------------------------------------------------------------- #




@project_experiments_router.get("", response_model=list[ExperimentRead])
def list_project_experiments(
    project_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> list[ExperimentRead]:
    """List experiments visible to the requester within ``project_id``.

    Returns shared experiments + the requester's private ones. Other
    users' private experiments are filtered out at the application
    layer regardless of org role — this is the "private experiments
    are strictly invisible" plan-locked decision.
    """
    organization_id, user_id = tenant_context
    _load_project(project_id, db, organization_id, user_id)

    rows = (
        db.query(ExperimentModel)
        .filter(ExperimentModel.project_id == project_id)
        .filter(ExperimentModel.organization_id == organization_id)
        .filter(ExperimentModel.deleted_at.is_(None))
        .order_by(ExperimentModel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    visible: list[ExperimentModel] = []
    for row in rows:
        if row.visibility == "private" and (
            user_id is None or str(row.owner_user_id) != str(user_id)
        ):
            continue
        visible.append(row)
    return [to_read(r) for r in visible]


@project_experiments_router.post(
    "",
    response_model=ExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_experiment(
    project_id: uuid.UUID,
    payload: ExperimentCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> ExperimentRead:
    """Create a new (header-only, no versions yet) experiment.

    ``project_id`` comes from the path. Owner is the authenticated
    user. Visibility defaults to ``private`` per the plan-locked
    decision so a fresh experiment never accidentally hits the team's
    radar before its first save.
    """
    organization_id, user_id = tenant_context
    _load_project(project_id, db, organization_id, user_id)

    db_experiment = ExperimentModel(
        project_id=project_id,
        organization_id=uuid.UUID(organization_id),
        owner_user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
        versions=[],
    )
    db.add(db_experiment)
    db.flush()
    db.refresh(db_experiment)
    return to_read(db_experiment)


__all__ = ["router", "project_experiments_router"]

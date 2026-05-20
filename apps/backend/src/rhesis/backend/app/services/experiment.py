"""Service-layer helpers for experiment lookup, validation, and resolution.

Sits between the route layer and the ORM so the visibility, project
scoping, environment-bind, and resolver invariants are enforced once and
shared across:

- ``GET /experiments/{id}`` and friends (visibility 404)
- ``POST /experiments/{id}/versions`` (idempotent append, optimistic
  concurrency)
- ``PUT /projects/{id}/parameters/environments/{name}`` (only shared
  experiments + version-must-exist)
- ``DELETE /experiments/{id}`` and visibility flips (refuse if an environment
  points here)
- ``GET /projects/{id}/parameters/resolve`` (single canonical resolver
  used by SDK, run-snapshot, and templating)

Keeping this off the routes lets the same logic be re-used by the
backend execute path that snapshots resolved values into a TestRun
without round-tripping through HTTP.
"""

from __future__ import annotations

import datetime as _dt
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import DetachedInstanceError

from rhesis.backend.app import crud, models
from rhesis.backend.app.models.experiment import Experiment
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.schemas.parameters import (
    BuiltInEnvironment,
    EnvironmentPointer,
    ExperimentDetail,
    ExperimentRead,
    ExperimentProject,
    ExperimentSummary,
    ExperimentVersion,
    ParameterSchema,
    ProjectEnvironments,
    ResolveResponse,
    canonical_hash,
    canonical_schema_fingerprint,
    unwrap_parameter_values_for_wire,
    validate_environment_name,
    validate_values_against_schema,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Visibility-aware lookup                                                     #
# --------------------------------------------------------------------------- #


def get_visible_experiment(
    db: Session,
    experiment_id: uuid.UUID,
    *,
    organization_id: str,
    user_id: str,
) -> Experiment:
    """Return ``experiment_id`` only if the requester may see it.

    Visibility model (plan-locked):

    - Shared experiments are visible to every project-org member.
    - Private experiments are visible only to their owner.
    - Anything else surfaces as 404 (never 403). Returning 404 keeps
      experiment existence from leaking across users / orgs.
    """
    db_experiment = crud.get_item(
        db,
        Experiment,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    if db_experiment.visibility == "private" and (
        user_id is None or str(db_experiment.owner_user_id) != str(user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    return db_experiment


def get_visible_experiment_in_project(
    db: Session,
    *,
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    organization_id: str,
    user_id: str,
) -> Experiment:
    """Visibility-aware lookup that also enforces project scoping.

    Used by the resolver and any cross-resource handler that takes a
    project id from the URL and an experiment id from the query: the
    experiment must belong to the requested project. Mismatch → 404
    (not 403) so existence isn't leaked across projects.
    """
    db_experiment = get_visible_experiment(
        db,
        experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if str(db_experiment.project_id) != str(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )
    return db_experiment


# --------------------------------------------------------------------------- #
# Version helpers                                                             #
# --------------------------------------------------------------------------- #


def latest_version(db_experiment: Experiment) -> ExperimentVersion | None:
    """Return the most recently appended version, or ``None`` if empty."""
    versions = db_experiment.versions or []
    if not versions:
        return None
    last = versions[-1]
    if isinstance(last, ExperimentVersion):
        return last
    return ExperimentVersion.model_validate(last)


def find_version(db_experiment: Experiment, version: str) -> ExperimentVersion:
    """Look up a single version by content hash; 404 if absent."""
    for entry in db_experiment.versions or []:
        candidate = (
            entry
            if isinstance(entry, ExperimentVersion)
            else ExperimentVersion.model_validate(entry)
        )
        if candidate.version == version:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Experiment version not found",
    )


# --------------------------------------------------------------------------- #
# Append a new version (idempotent + optimistic-concurrency safe)             #
# --------------------------------------------------------------------------- #


@dataclass
class AppendResult:
    version: ExperimentVersion
    created: bool
    """``True`` iff a new entry was appended; ``False`` for idempotent no-ops."""


def append_version(
    db: Session,
    *,
    db_experiment: Experiment,
    project_schema: ParameterSchema,
    raw_values: dict[str, Any],
    message: str | None,
    parent_version: str | None,
    created_by_user_id: uuid.UUID,
) -> AppendResult:
    """Validate, hash, idempotency-check, then append (or no-op).

    Concurrency: locks the experiment row with ``SELECT ... FOR
    UPDATE`` before re-reading versions and bumping ``update_count``.
    Two concurrent committers therefore serialize correctly — one
    sees the other's append and either no-ops on identical hash or
    appends as the next entry. The ``update_count`` bump is what the
    plan calls the "optimistic-concurrency guard"; it's a strictly
    monotonic integer that downstream tooling can use to detect "row
    was modified since I read it" without re-comparing the JSONB
    array.

    Idempotency: if the latest version's hash equals the new one, the
    server returns the existing entry verbatim. Saving the same
    values twice is a no-op even on a fast double-click.
    """
    typed_values = validate_values_against_schema(raw_values, project_schema)
    fingerprint = canonical_schema_fingerprint(project_schema)
    new_version_id = canonical_hash(fingerprint, typed_values)

    locked = db.query(Experiment).filter(Experiment.id == db_experiment.id).with_for_update().one()
    versions: list[ExperimentVersion] = [
        v if isinstance(v, ExperimentVersion) else ExperimentVersion.model_validate(v)
        for v in (locked.versions or [])
    ]

    if versions and versions[-1].version == new_version_id:
        return AppendResult(version=versions[-1], created=False)

    # Validate explicit parent_version exists in the versions array
    if parent_version is not None and versions:
        known = {v.version for v in versions}
        if parent_version not in known:
            raise ValueError(
                f"parent_version {parent_version!r} does not exist"
                " in this experiment's version history"
            )

    new_entry = ExperimentVersion(
        version=new_version_id,
        schema_fingerprint=fingerprint,
        values=typed_values,
        parent_version=parent_version or (versions[-1].version if versions else None),
        message=message,
        created_at=_dt.datetime.now(_dt.timezone.utc),
        created_by_user_id=created_by_user_id,
    )
    # Reassign with a fresh list so SQLAlchemy's identity-based dirty
    # tracking flags ``versions`` for write. In-place ``.append`` is
    # invisible to the change detector because the column value's
    # Python identity stays the same.
    locked.versions = [*versions, new_entry]
    locked.update_count = (locked.update_count or 0) + 1
    db.add(locked)
    db.commit()
    db.refresh(locked)
    return AppendResult(version=new_entry, created=True)


# --------------------------------------------------------------------------- #
# Project environments                                                        #
# --------------------------------------------------------------------------- #


def coerce_environments(project: Project) -> ProjectEnvironments:
    """Safely coerce the project's ``parameter_environments`` JSONB to a typed model."""
    raw = project.parameter_environments
    if isinstance(raw, ProjectEnvironments):
        return raw
    if raw is None:
        return ProjectEnvironments()
    return ProjectEnvironments.model_validate(raw)


def coerce_schema(project: Project) -> ParameterSchema:
    """Safely coerce the project's ``parameters_schema`` JSONB to a typed model."""
    raw = project.parameters_schema
    if isinstance(raw, ParameterSchema):
        return raw
    if raw is None:
        return ParameterSchema()
    return ParameterSchema.model_validate(raw)


# Keep private aliases for backward compat within this module
_coerce_environments = coerce_environments
_coerce_schema = coerce_schema


def environments_pointing_at_experiment(
    project: Project,
    experiment_id: uuid.UUID,
) -> list[str]:
    """Names of project environments currently pointing at ``experiment_id``.

    Skips entries with a ``None`` pointer (registered-but-unbound names);
    those by definition aren't keeping any experiment alive.
    """
    environments = _coerce_environments(project)
    return sorted(
        name
        for name, ptr in environments.environments.items()
        if ptr is not None and str(ptr.experiment_id) == str(experiment_id)
    )


def bind_environment(
    db: Session,
    *,
    project: Project,
    environment_name: str,
    pointer: EnvironmentPointer,
    organization_id: str,
    user_id: str,
) -> ProjectEnvironments:
    """Set ``project.parameter_environments[environment_name] = pointer``.

    Validates the name shape (lowercase alphanumerics plus ``.``/``_``/``-``,
    starting with an alphanumeric, up to 63 chars), that the referenced
    experiment is shared, and that the version exists. The HTTP route
    re-validates the name via FastAPI ``Path(pattern=...)`` so most
    callers fail fast at the boundary; the explicit call here guards
    any non-HTTP entry point (background tasks, future RPC, tests).
    """
    try:
        validate_environment_name(environment_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    db_experiment = get_visible_experiment_in_project(
        db,
        project_id=project.id,
        experiment_id=pointer.experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_experiment.visibility != "shared":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only shared experiments may be promoted to an environment. "
                "Share the experiment first."
            ),
        )
    find_version(db_experiment, pointer.version)

    # Materialize a fresh ProjectEnvironments instance so SQLAlchemy sees the
    # ORM attribute change. Mutating the existing model in place is
    # invisible to the dirty-tracking layer because the attribute
    # value is identity-equal before and after the mutation; the
    # PydanticColumn TypeDecorator only fires `process_bind_param` on
    # an attribute set, not on in-place updates.
    current = _coerce_environments(project)
    new_map = dict(current.environments)
    new_map[environment_name] = pointer
    project.parameter_environments = ProjectEnvironments(environments=new_map)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _coerce_environments(project)


def register_environment(
    db: Session,
    *,
    project: Project,
    environment_name: str,
) -> ProjectEnvironments:
    """Add ``environment_name`` to the project with a ``None`` pointer.

    Used to declare a custom environment name upfront so it shows in the
    project UI as an "Unbound" row that the user can later Promote onto.
    Refuses with **409** if the name already exists (either bound or
    already registered), and with **422** if the name shape is wrong.

    Built-in names (see :attr:`BuiltInEnvironment.ALL`) cannot be
    "registered" — they're always present as a frontend overlay — so
    the route returns 409 if asked to register one. This keeps the
    server's stored state minimal and avoids spurious null entries that
    add noise to ``GET`` responses.
    """
    try:
        validate_environment_name(environment_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if environment_name in BuiltInEnvironment.ALL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Environment {environment_name!r} is a built-in name "
                "and is always available; you don't need to register it."
            ),
        )

    current = _coerce_environments(project)
    if environment_name in current.environments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Environment {environment_name!r} already exists. Use "
                "PUT /environments/{name} to bind a different experiment."
            ),
        )

    new_map: dict[str, Any] = dict(current.environments)
    new_map[environment_name] = None
    project.parameter_environments = ProjectEnvironments(environments=new_map)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _coerce_environments(project)


def unbind_environment(
    db: Session,
    *,
    project: Project,
    environment_name: str,
) -> ProjectEnvironments:
    """Remove ``environment_name`` from the project's environment map (idempotent)."""
    current = _coerce_environments(project)
    new_map = dict(current.environments)
    new_map.pop(environment_name, None)
    project.parameter_environments = ProjectEnvironments(environments=new_map)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _coerce_environments(project)


# --------------------------------------------------------------------------- #
# Visibility flip / delete preconditions                                      #
# --------------------------------------------------------------------------- #


def assert_no_active_environments(
    project: Project,
    experiment_id: uuid.UUID,
    *,
    action: str,
) -> None:
    """Refuse with 409 if any project environment still points at this experiment.

    Used to guard the two destructive operations that would break the
    "environments point only at shared experiments and only at existing
    versions" invariant: unsharing an experiment, and deleting it.
    """
    bound = environments_pointing_at_experiment(project, experiment_id)
    if bound:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot {action} experiment while these environments still"
                f" point at it: {bound}. Move or unbind the environments first."
            ),
        )


# --------------------------------------------------------------------------- #
# Canonical resolver                                                          #
# --------------------------------------------------------------------------- #


def resolve_parameters(
    db: Session,
    *,
    project: Project,
    environment: str | None,
    experiment_id: uuid.UUID | None,
    version: str | None,
    organization_id: str,
    user_id: str,
) -> ResolveResponse:
    """The single canonical resolver used by the SDK and run-snapshot.

    Precedence: ``version`` (immutable) > ``experiment_id`` (latest
    version of that experiment) > ``environment`` (lookup in
    :class:`ProjectEnvironments`) > implicit
    :attr:`BuiltInEnvironment.DEFAULT`. The handler
    walks the precedence top-down and returns as soon as one of them
    resolves; it never silently falls back to ``default`` after a
    user-supplied filter fails — that would mask a typo as an environment
    promotion.

    Visibility: resolving by ``experiment_id`` or ``version`` against
    a private experiment owned by another user surfaces as 404.
    Resolving by environment is open to all project members because the
    environment is the *public face*; the underlying experiment is
    necessarily shared (enforced at bind time and protected by the
    no-active-environment rule).
    """
    project_schema = _coerce_schema(project)

    if version is not None and experiment_id is None:
        # Resolving a version requires knowing which experiment it
        # belongs to. We walk shared+owned experiments in this project
        # and pick the unique match — versions are content hashes so
        # collisions across experiments are vanishingly rare, and
        # plan-locked invariants don't promise uniqueness anyway.
        match = _find_experiment_holding_version(
            db,
            project_id=project.id,
            version=version,
            organization_id=organization_id,
            user_id=user_id,
        )
        return _build_resolve_response(
            schema=project_schema,
            experiment=match,
            version_entry=find_version(match, version),
            source="version",
            source_environment=None,
        )

    if experiment_id is not None:
        db_experiment = get_visible_experiment_in_project(
            db,
            project_id=project.id,
            experiment_id=experiment_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if version is not None:
            entry = find_version(db_experiment, version)
            return _build_resolve_response(
                schema=project_schema,
                experiment=db_experiment,
                version_entry=entry,
                source="version",
                source_environment=None,
            )
        latest = latest_version(db_experiment)
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment has no versions yet",
            )
        return _build_resolve_response(
            schema=project_schema,
            experiment=db_experiment,
            version_entry=latest,
            source="experiment_id",
            source_environment=None,
        )

    environment_name = environment or BuiltInEnvironment.DEFAULT
    environments = _coerce_environments(project)
    pointer = environments.environments.get(environment_name)
    if pointer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment {environment_name!r} is not bound for this project",
        )
    db_experiment = get_visible_experiment_in_project(
        db,
        project_id=project.id,
        experiment_id=pointer.experiment_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    entry = find_version(db_experiment, pointer.version)
    return _build_resolve_response(
        schema=project_schema,
        experiment=db_experiment,
        version_entry=entry,
        source="environment",
        source_environment=environment_name,
    )


def _find_experiment_holding_version(
    db: Session,
    *,
    project_id: uuid.UUID,
    version: str,
    organization_id: str,
    user_id: str,
) -> Experiment:
    """Locate the project experiment whose ``versions`` contains ``version``.

    A linear scan is acceptable for v1 — most projects carry tens of
    experiments at most. If the count grows, we add a per-org btree
    expression index on ``experiment.versions`` similar to the run
    side, but it isn't on the critical path right now.
    """
    candidates = (
        db.query(Experiment)
        .filter(Experiment.project_id == project_id)
        .filter(Experiment.organization_id == organization_id)
        .all()
    )
    for cand in candidates:
        if cand.visibility == "private" and (
            user_id is None or str(cand.owner_user_id) != str(user_id)
        ):
            continue
        for entry in cand.versions or []:
            v = entry.version if isinstance(entry, ExperimentVersion) else entry.get("version")
            if v == version:
                return cand
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Experiment version not found in this project",
    )


def _build_resolve_response(
    *,
    schema: ParameterSchema,
    experiment: Experiment,
    version_entry: ExperimentVersion,
    source: str,
    source_environment: str | None,
) -> ResolveResponse:
    return ResolveResponse(
        schema=schema,
        values=version_entry.values,
        experiment_id=experiment.id,
        version=version_entry.version,
        source=source,
        source_environment=source_environment,
    )


# --------------------------------------------------------------------------- #
# Read shapes                                                                 #
# --------------------------------------------------------------------------- #


def to_summary(
    db_experiment: Experiment,
    *,
    version: str,
    source_environment: str | None,
) -> ExperimentSummary:
    """Compact shape used inline on TestRun responses."""
    return ExperimentSummary(
        id=db_experiment.id,
        name=db_experiment.name,
        version=version,
        source_environment=source_environment,
        visibility=db_experiment.visibility,  # type: ignore[arg-type]
    )


def experiment_summary_dict_from_run_attributes(
    attributes: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build the ``experiment_summary`` object from a run's JSONB attributes.

    Values are denormalized at snapshot time so list/detail responses do
    not need a second query to the experiment row.
    """
    if not attributes:
        return None
    exp_id = attributes.get("parameter_experiment_id")
    if not exp_id:
        return None
    src_env = attributes.get("parameter_source_environment")
    if src_env is None:
        src_env = attributes.get("parameter_source_label")
    return {
        "id": exp_id,
        "name": attributes.get("parameter_experiment_name") or "Experiment",
        "version": attributes.get("parameter_version") or "",
        "source_environment": src_env,
        "visibility": attributes.get("parameter_experiment_visibility") or "shared",
    }


@dataclass(frozen=True)
class ParameterSnapshot:
    """Output of :func:`apply_parameter_snapshot_to_run_attributes`.

    ``attributes`` is the merged JSONB blob to persist on
    :class:`~rhesis.backend.app.models.test_run.TestRun.attributes`.
    ``experiment_id`` is the UUID to set on the relational column, or
    ``None`` when the run is not associated with an experiment.
    """

    attributes: dict[str, Any]
    experiment_id: uuid.UUID | None


def apply_parameter_snapshot_to_run_attributes(
    db: Session,
    *,
    test_config: models.TestConfiguration,
    attributes: dict[str, Any],
    organization_id: str,
    user_id: str,
) -> ParameterSnapshot:
    """Resolve ``parameters_ref`` on the configuration and merge into run attrs.

    Called exactly once when a :class:`~rhesis.backend.app.models.test_run.TestRun`
    is created so the worker and connector read only the snapshot -- never
    re-resolve at execution time.

    Returns a :class:`ParameterSnapshot` carrying both the merged attribute
    dict (immutable record of what was resolved) and the experiment UUID
    that should be stamped onto the run's relational ``experiment_id``
    column. When no ``parameters_ref`` is configured, the original
    attributes are returned unchanged and ``experiment_id`` is ``None``.

    Raises:
        ValueError: On resolver failures (missing project, bad ref, HTTP-style
            denial converted from :class:`fastapi.HTTPException`).
    """
    cfg_attrs = test_config.attributes or {}
    ref = cfg_attrs.get("parameters_ref")
    if not ref or not isinstance(ref, dict):
        return ParameterSnapshot(attributes=attributes, experiment_id=None)

    from rhesis.backend.app.models.endpoint import Endpoint

    endpoint = db.get(Endpoint, test_config.endpoint_id)
    if endpoint is None or endpoint.project_id is None:
        raise ValueError("Cannot resolve parameters: endpoint or project missing")

    project = crud.get_project(
        db,
        project_id=endpoint.project_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if project is None:
        raise ValueError("Cannot resolve parameters: project not found")

    experiment_uuid: uuid.UUID | None = None
    raw_exp = ref.get("experiment_id")
    if raw_exp:
        experiment_uuid = uuid.UUID(str(raw_exp))

    version = ref.get("version")
    if isinstance(version, str) and not version.strip():
        version = None

    environment = ref.get("environment")
    if environment is None:
        environment = ref.get("label")

    try:
        resolved = resolve_parameters(
            db,
            project=project,
            environment=environment,
            experiment_id=experiment_uuid,
            version=version,
            organization_id=organization_id,
            user_id=user_id,
        )
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc

    exp_row = db.get(Experiment, resolved.experiment_id)
    exp_name = exp_row.name if exp_row else "Experiment"
    exp_vis = str(exp_row.visibility) if exp_row else "shared"

    merged = {**attributes}
    merged["parameters"] = unwrap_parameter_values_for_wire(resolved.values)
    merged["parameter_version"] = resolved.version
    # ``parameter_experiment_id`` stays in attributes as part of the
    # immutable resolution record. The relational ``experiment_id`` column
    # carries the same value but is the queryable / joinable surface.
    merged["parameter_experiment_id"] = str(resolved.experiment_id)
    merged["parameter_source"] = resolved.source
    if resolved.source_environment is not None:
        merged["parameter_source_environment"] = resolved.source_environment
    merged["parameter_schema"] = resolved.schema_.model_dump(mode="json")
    merged["parameter_experiment_name"] = exp_name
    merged["parameter_experiment_visibility"] = exp_vis
    return ParameterSnapshot(attributes=merged, experiment_id=resolved.experiment_id)


def connector_execute_extras_from_run_attributes(
    attributes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Subset of run attributes forwarded on the connector ``ExecuteTestMessage``."""
    if not attributes or not attributes.get("parameter_experiment_id"):
        return {}
    params = attributes.get("parameters") or {}
    schema = attributes.get("parameter_schema")
    src_env = attributes.get("parameter_source_environment")
    if src_env is None:
        src_env = attributes.get("parameter_source_label")
    extras: dict[str, Any] = {
        "parameters": params,
        "parameter_version": attributes.get("parameter_version"),
        "parameter_experiment_id": attributes.get("parameter_experiment_id"),
        "parameter_source": attributes.get("parameter_source"),
        "parameter_source_environment": src_env,
    }
    if schema is not None:
        extras["parameter_schema"] = schema
    return extras


def to_read(db_experiment: Experiment) -> ExperimentRead:
    """Convert a DB experiment row to the compact list/read shape."""
    last = latest_version(db_experiment)
    project: ExperimentProject | None = None
    project_name: str | None = None
    try:
        if db_experiment.project is not None:
            project = ExperimentProject(
                id=db_experiment.project.id,
                name=db_experiment.project.name,
            )
            project_name = db_experiment.project.name
    except DetachedInstanceError:
        pass
    return ExperimentRead(
        id=db_experiment.id,
        name=db_experiment.name,
        description=db_experiment.description,
        visibility=db_experiment.visibility,  # type: ignore[arg-type]
        project_id=db_experiment.project_id,
        owner_user_id=db_experiment.owner_user_id,
        organization_id=db_experiment.organization_id,
        project=project,
        project_name=project_name,
        versions_count=len(db_experiment.versions or []),
        latest_version=last.version if last else None,
        created_at=db_experiment.created_at,
        updated_at=db_experiment.updated_at,
    )


def to_detail(db_experiment: Experiment) -> ExperimentDetail:
    """Convert a DB experiment row to the detail shape (with versions)."""
    versions: list[ExperimentVersion] = [
        v if isinstance(v, ExperimentVersion) else ExperimentVersion.model_validate(v)
        for v in (db_experiment.versions or [])
    ]
    last = versions[-1] if versions else None
    project: ExperimentProject | None = None
    project_name: str | None = None
    try:
        if db_experiment.project is not None:
            project = ExperimentProject(
                id=db_experiment.project.id,
                name=db_experiment.project.name,
            )
            project_name = db_experiment.project.name
    except DetachedInstanceError:
        pass
    return ExperimentDetail(
        id=db_experiment.id,
        name=db_experiment.name,
        description=db_experiment.description,
        visibility=db_experiment.visibility,  # type: ignore[arg-type]
        project_id=db_experiment.project_id,
        owner_user_id=db_experiment.owner_user_id,
        organization_id=db_experiment.organization_id,
        project=project,
        project_name=project_name,
        versions_count=len(versions),
        latest_version=last.version if last else None,
        created_at=db_experiment.created_at,
        updated_at=db_experiment.updated_at,
        versions=versions,
    )


__all__ = [
    "AppendResult",
    "append_version",
    "apply_parameter_snapshot_to_run_attributes",
    "assert_no_active_environments",
    "bind_environment",
    "coerce_environments",
    "coerce_schema",
    "connector_execute_extras_from_run_attributes",
    "experiment_summary_dict_from_run_attributes",
    "find_version",
    "get_visible_experiment",
    "get_visible_experiment_in_project",
    "environments_pointing_at_experiment",
    "latest_version",
    "resolve_parameters",
    "to_detail",
    "to_read",
    "to_summary",
    "unbind_environment",
]

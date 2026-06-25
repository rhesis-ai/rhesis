"""Parameters facade — the public entry point for parameter resolution.

``Parameters.get()`` resolves parameters from the backend (or cache)
and returns a :class:`~rhesis.sdk.models.parameters.ResolvedParameters`
instance.
"""

from __future__ import annotations

import logging
import os
import uuid as _uuid
from typing import Any

import requests

from rhesis.sdk.config import get_api_key, get_base_url
from rhesis.sdk.models.parameters import (
    ParameterSchema,
    ProjectEnvironments,
    ResolvedParameters,
    ResolveResponse,
)
from rhesis.sdk.parameters._cache import ParameterCache

logger = logging.getLogger(__name__)

_cache = ParameterCache()


def _resolve_project_id(
    project: str | None = None,
    *,
    project_id: str | None = None,
) -> str:
    """Return a project UUID string, resolving by name if needed."""
    if project and project_id:
        raise ValueError("Pass 'project' (name or id) or 'project_id', not both")
    if project_id:
        return str(project_id)
    if project:
        try:
            _uuid.UUID(project)
            return project
        except ValueError:
            pass
        from rhesis.sdk.entities import Projects

        proj = Projects.pull(name=project)
        return proj.id
    raise ValueError("Either 'project' (name or id) or 'project_id' must be provided")


class Parameters:
    """Facade for resolving project-scoped parameter values.

    All methods are class methods — no instantiation needed::

        params = Parameters.get("My App")
        params.model          # "gpt-4o"
        params.temperature    # 0.7

    *project* accepts a project name or UUID string.  Use *project_id*
    when you already have the UUID::

        params = Parameters.get(project_id="550e8400-...")
    """

    @classmethod
    def get(
        cls,
        project: str | None = None,
        *,
        project_id: str | None = None,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> ResolvedParameters:
        """Resolve parameters and return a typed mapping.

        *project* accepts a project name **or** UUID string.
        Use *project_id* when you already have the UUID::

            params = Parameters.get("My App")
            params = Parameters.get(project_id="550e8400-...")

        Resolution order (first non-``None`` wins):

        1. ``version`` — immutable version pin (e.g. ``"v3"``)
        2. ``experiment_id`` — latest version of that experiment
        3. ``environment`` — movable pointer (``"default"`` when omitted)

        Results are cached: immutable ``version`` lookups live forever;
        ``environment`` and ``experiment_id`` lookups honour a TTL
        (default 60 s). Call :meth:`invalidate` to force a re-fetch.
        """
        pid = _resolve_project_id(project, project_id=project_id)
        if environment is None and experiment_id is None and version is None:
            pinned = os.getenv("RHESIS_PARAMETERS_ENVIRONMENT") or os.getenv(
                "RHESIS_PARAMETERS_LABEL"
            )
            if pinned:
                environment = pinned

        cached = _cache.get(
            pid,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        if cached is not None:
            return cached

        response = cls._fetch(
            pid,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        resolved = ResolvedParameters.from_response(response)
        _cache.put(
            pid,
            resolved,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        return resolved

    @classmethod
    def schema(
        cls,
        project: str | None = None,
        *,
        project_id: str | None = None,
    ) -> ParameterSchema:
        """Fetch the project's parameter schema."""
        pid = _resolve_project_id(project, project_id=project_id)
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{pid}/parameters/schema"
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        return ParameterSchema.model_validate(resp.json())

    @classmethod
    def environments(
        cls,
        project: str | None = None,
        *,
        project_id: str | None = None,
    ) -> ProjectEnvironments:
        """Fetch the project's bound environments."""
        pid = _resolve_project_id(project, project_id=project_id)
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{pid}/parameters/environments"
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        return ProjectEnvironments.model_validate(resp.json())

    @classmethod
    def put_schema(
        cls,
        project: str | None = None,
        schema: ParameterSchema | None = None,
        *,
        project_id: str | None = None,
    ) -> None:
        """Push a parameter schema to the project.

        Overwrites any existing schema on the project.
        """
        pid = _resolve_project_id(project, project_id=project_id)
        if schema is None:
            raise ValueError("schema is required")
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{pid}/parameters/schema"
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=schema.model_dump(mode="json"),
        )
        resp.raise_for_status()

    @classmethod
    def put_environment(
        cls,
        project: str | None = None,
        environment: str | None = None,
        *,
        project_id: str | None = None,
        experiment_id: str,
        version: str,
    ) -> None:
        """Bind *environment* to a specific (experiment_id, version) pair."""
        pid = _resolve_project_id(project, project_id=project_id)
        if environment is None:
            raise ValueError("environment is required")
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{pid}/parameters/environments/{environment}"
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "experiment_id": str(experiment_id),
                "version": version,
            },
        )
        resp.raise_for_status()

    @classmethod
    def invalidate(cls, project: str | None = None) -> None:
        """Drop cached entries for *project* (or all projects)."""
        _cache.invalidate(project)

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _fetch(
        cls,
        project: str,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> ResolveResponse:
        base = get_base_url().rstrip("/")
        api_key = get_api_key()

        url = f"{base}/projects/{project}/parameters/resolve"
        params: dict[str, Any] = {}
        if version is not None:
            params["version"] = version
        if experiment_id is not None:
            params["experiment_id"] = str(experiment_id)
        if environment is not None:
            params["environment"] = environment

        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
        )
        resp.raise_for_status()
        return ResolveResponse.model_validate(resp.json())

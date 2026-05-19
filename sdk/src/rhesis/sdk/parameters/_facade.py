"""Parameters facade — the public entry point for parameter resolution.

``Parameters.get()`` resolves parameters from the backend (or cache)
and returns a :class:`~rhesis.sdk.models.parameters.ResolvedParameters`
instance.
"""

from __future__ import annotations

import logging
import os
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


class Parameters:
    """Facade for resolving project-scoped parameter values.

    All methods are class methods — no instantiation needed::

        from rhesis.sdk.models.parameters import BuiltInEnvironment

        params = Parameters.get(
            project="chatbot-demo",
            environment=BuiltInEnvironment.DEFAULT,
        )
        print(params["temperature"])

    Plain strings work too (``environment="default"``);
    :class:`BuiltInEnvironment` is purely a tidy namespace for callers
    who prefer not to hand-write the built-in names.
    """

    @classmethod
    def get(
        cls,
        project: str,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> ResolvedParameters:
        """Resolve parameters for *project* and return a typed mapping.

        Resolution order (first non-``None`` wins):

        1. ``version`` — immutable content-hash pin
        2. ``experiment_id`` — latest version of that experiment
        3. ``environment`` — movable pointer (``"default"`` when omitted)

        When *version*, *experiment_id*, and *environment* are all omitted,
        ``RHESIS_PARAMETERS_ENVIRONMENT`` is consulted (with legacy
        ``RHESIS_PARAMETERS_LABEL`` as a fallback) so deploys can pin an
        environment without code changes.

        Results are cached: immutable ``version`` lookups live forever;
        ``environment`` and ``experiment_id`` lookups honour a TTL (default
        60 s). Call :meth:`invalidate` to force a re-fetch.
        """
        if (
            environment is None
            and experiment_id is None
            and version is None
        ):
            pinned = os.getenv("RHESIS_PARAMETERS_ENVIRONMENT") or os.getenv(
                "RHESIS_PARAMETERS_LABEL"
            )
            if pinned:
                environment = pinned

        cached = _cache.get(
            project,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        if cached is not None:
            return cached

        response = cls._fetch(
            project,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        resolved = ResolvedParameters.from_response(response)
        _cache.put(
            project,
            resolved,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )
        return resolved

    @classmethod
    def schema(cls, project: str) -> ParameterSchema:
        """Fetch the project's parameter schema."""
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{project}/parameters/schema"
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {api_key}"}
        )
        resp.raise_for_status()
        return ParameterSchema.model_validate(resp.json())

    @classmethod
    def environments(cls, project: str) -> ProjectEnvironments:
        """Fetch the project's bound environments."""
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{project}/parameters/environments"
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {api_key}"}
        )
        resp.raise_for_status()
        return ProjectEnvironments.model_validate(resp.json())

    @classmethod
    def put_schema(cls, project: str, schema: ParameterSchema) -> None:
        """Push a parameter schema to the project.

        Overwrites any existing schema on the project.
        """
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{project}/parameters/schema"
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=schema.model_dump(mode="json"),
        )
        resp.raise_for_status()

    @classmethod
    def put_environment(
        cls,
        project: str,
        environment: str,
        *,
        experiment_id: str,
        version: str,
    ) -> None:
        """Bind *environment* to a specific (experiment_id, version) pair."""
        base = get_base_url().rstrip("/")
        api_key = get_api_key()
        url = f"{base}/projects/{project}/parameters/environments/{environment}"
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

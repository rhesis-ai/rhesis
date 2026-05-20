"""Experiment entity and collection for the Rhesis SDK.

Experiments are named bundles of parameter values that mint immutable
versions on each save.  This entity follows the same BaseEntity /
BaseCollection pattern used by all other SDK entities.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Optional

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors

logger = logging.getLogger(__name__)

ENDPOINT = Endpoints.EXPERIMENTS


class Experiment(BaseEntity):
    """An experiment — a named bundle of parameter values for a project.

    Examples::

        exp = Experiment(name="tuning-v2", project_id="<uuid>")
        exp.push()
        exp.commit({"temperature": 0.9, "model": "gpt-4o"}, message="bump temp")
        exp.share()
        exp.promote(environment="staging")
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    visibility: Optional[str] = "private"
    owner_user_id: Optional[str] = None
    versions_count: Optional[int] = 0
    latest_version: Optional[str] = None
    versions: Optional[list[dict[str, Any]]] = None

    # ------------------------------------------------------------------ #
    # Project-scoped creation                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def _create(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Create via ``POST /projects/{project_id}/experiments``."""
        project_id = data.get("project_id")
        if not project_id:
            raise ValueError("project_id is required to create an experiment")
        client = APIClient()
        import requests as _requests

        url = client.get_url(f"projects/{project_id}/experiments")
        resp = _requests.post(url, headers=client.headers, json=data)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # Versions                                                             #
    # ------------------------------------------------------------------ #

    @handle_http_errors
    def commit(
        self,
        values: dict[str, Any],
        *,
        message: str | None = None,
        parent_version: str | None = None,
    ) -> dict[str, Any]:
        """Append a new immutable version to this experiment.

        Returns the version entry (including its content hash).
        """
        payload: dict[str, Any] = {"values": values}
        if message is not None:
            payload["message"] = message
        if parent_version is not None:
            payload["parent_version"] = parent_version
        client = APIClient()
        version_data = client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/versions",
            data=payload,
        )
        self.latest_version = version_data.get("version")
        return version_data

    @handle_http_errors
    def list_versions(self) -> list[dict[str, Any]]:
        """Return all versions for this experiment, oldest to newest."""
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/versions",
        )

    @handle_http_errors
    def latest_version_data(self) -> dict[str, Any] | None:
        """Fetch the latest version entry, or ``None`` if no versions."""
        versions = self.list_versions()
        return versions[-1] if versions else None

    @handle_http_errors
    def get_version(self, version: str) -> dict[str, Any]:
        """Fetch a single version by content hash."""
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/versions/{version}",
        )

    # ------------------------------------------------------------------ #
    # Visibility                                                           #
    # ------------------------------------------------------------------ #

    @handle_http_errors
    def share(self) -> None:
        """Set visibility to ``shared``."""
        client = APIClient()
        client.send_request(
            endpoint=self.endpoint,
            method=Methods.PATCH,
            url_params=str(self.id),
            data={"visibility": "shared"},
        )
        self.visibility = "shared"

    @handle_http_errors
    def unshare(self) -> None:
        """Set visibility back to ``private``."""
        client = APIClient()
        client.send_request(
            endpoint=self.endpoint,
            method=Methods.PATCH,
            url_params=str(self.id),
            data={"visibility": "private"},
        )
        self.visibility = "private"

    # ------------------------------------------------------------------ #
    # Environment promotion                                                #
    # ------------------------------------------------------------------ #

    @handle_http_errors
    def promote(self, environment: str = "default") -> None:
        """Bind this experiment's latest version to *environment*.

        The experiment must be shared and must have at least one version.
        """
        if self.latest_version is None:
            raise ValueError("Experiment has no versions to promote")
        client = APIClient()
        import requests as _requests

        url = client.get_url(f"projects/{self.project_id}/parameters/environments/{environment}")
        resp = _requests.put(
            url,
            headers=client.headers,
            json={
                "experiment_id": str(self.id),
                "version": self.latest_version,
            },
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------ #
    # Results                                                              #
    # ------------------------------------------------------------------ #

    @handle_http_errors
    def results(
        self,
        *,
        group_by: str = "run",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Aggregate test-run results for this experiment.

        Args:
            group_by: ``"run"`` (default) returns one entry per test run.
                ``"version"`` groups runs by parameter version and includes
                diffs against each version's parent.
            limit: Maximum number of test runs to include (1–1000).

        Returns:
            ``{"items": [...]}`` where each item is a run (or version
            group) enriched with ``stats`` counters (total, passed,
            failed, errors).
        """
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/results",
            params={"group_by": group_by, "limit": limit},
        )

    # ------------------------------------------------------------------ #
    # Convenience                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def publish(
        cls,
        *,
        name: str,
        project_id: str,
        values: dict[str, Any],
        message: str | None = None,
        environment: str = "default",
        description: str | None = None,
    ) -> "Experiment":
        """One-liner: create -> commit -> share -> promote.

        Returns the fully-published experiment::

            exp = Experiment.publish(
                name="tuning-v3",
                project_id="<uuid>",
                values={"temperature": 0.9},
                environment="default",
            )
        """
        exp = cls(
            name=name,
            project_id=project_id,
            description=description,
        )
        exp.push()
        exp.commit(values, message=message)
        exp.share()
        exp.promote(environment=environment)
        return exp


class Experiments(BaseCollection):
    """Collection helper for experiments."""

    entity_class = Experiment
    endpoint: ClassVar[Endpoints] = ENDPOINT

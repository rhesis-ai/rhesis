"""Experiment entity and collection for the Rhesis SDK.

Experiments are named bundles of parameter values that mint immutable
versions on each save.  This entity follows the same BaseEntity /
BaseCollection pattern used by all other SDK entities.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Optional

from rhesis.sdk.clients import Endpoints
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
        exp.promote(label="staging")
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT

    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    visibility: Optional[str] = "private"
    owner_user_id: Optional[str] = None
    versions_count: Optional[int] = 0
    latest_version: Optional[str] = None
    versions: Optional[list[dict[str, Any]]] = None

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
        client = self._get_client()
        url = client.get_url(f"{self.endpoint.value}/{self.id}/versions")
        payload: dict[str, Any] = {"values": values}
        if message is not None:
            payload["message"] = message
        if parent_version is not None:
            payload["parent_version"] = parent_version
        import requests as _requests

        resp = _requests.post(url, headers=client.headers, json=payload)
        resp.raise_for_status()
        version_data = resp.json()
        self.latest_version = version_data.get("version")
        return version_data

    @handle_http_errors
    def latest_version_data(self) -> dict[str, Any] | None:
        """Fetch the latest version entry, or ``None`` if no versions."""
        client = self._get_client()
        url = client.get_url(f"{self.endpoint.value}/{self.id}/versions")
        import requests as _requests

        resp = _requests.get(url, headers=client.headers)
        resp.raise_for_status()
        versions = resp.json()
        return versions[-1] if versions else None

    @handle_http_errors
    def get_version(self, version: str) -> dict[str, Any]:
        """Fetch a single version by content hash."""
        client = self._get_client()
        url = client.get_url(
            f"{self.endpoint.value}/{self.id}/versions/{version}"
        )
        import requests as _requests

        resp = _requests.get(url, headers=client.headers)
        resp.raise_for_status()
        return resp.json()

    @handle_http_errors
    def share(self) -> None:
        """Set visibility to ``shared``."""
        self.visibility = "shared"
        client = self._get_client()
        url = client.get_url(f"{self.endpoint.value}/{self.id}")
        import requests as _requests

        resp = _requests.patch(
            url, headers=client.headers, json={"visibility": "shared"}
        )
        resp.raise_for_status()

    @handle_http_errors
    def unshare(self) -> None:
        """Set visibility back to ``private``."""
        self.visibility = "private"
        client = self._get_client()
        url = client.get_url(f"{self.endpoint.value}/{self.id}")
        import requests as _requests

        resp = _requests.patch(
            url, headers=client.headers, json={"visibility": "private"}
        )
        resp.raise_for_status()

    @classmethod
    def publish(
        cls,
        *,
        name: str,
        project_id: str,
        values: dict[str, Any],
        message: str | None = None,
        label: str = "default",
        description: str | None = None,
    ) -> "Experiment":
        """One-liner: create → commit → share → promote.

        Returns the fully-published experiment::

            exp = Experiment.publish(
                name="tuning-v3",
                project_id="<uuid>",
                values={"temperature": 0.9},
                label="default",
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
        exp.promote(label=label)
        return exp

    @handle_http_errors
    def promote(self, label: str = "default") -> None:
        """Bind this experiment's latest version to *label*.

        The experiment must be shared and must have at least one version.
        """
        if self.latest_version is None:
            raise ValueError("Experiment has no versions to promote")
        client = self._get_client()
        url = client.get_url(
            f"projects/{self.project_id}/parameters/labels/{label}"
        )
        import requests as _requests

        resp = _requests.put(
            url,
            headers=client.headers,
            json={
                "experiment_id": str(self.id),
                "version": self.latest_version,
            },
        )
        resp.raise_for_status()


class Experiments(BaseCollection):
    """Collection helper for experiments."""

    entity_class = Experiment
    endpoint: ClassVar[Endpoints] = ENDPOINT

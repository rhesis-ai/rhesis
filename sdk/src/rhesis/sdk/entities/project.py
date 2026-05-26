from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from rhesis.sdk.clients import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

if TYPE_CHECKING:
    from rhesis.sdk.models.parameters import (
        ParameterSchema,
        ResolvedParameters,
    )

ENDPOINT = Endpoints.PROJECTS


class Project(BaseEntity):
    """Project entity for interacting with the Rhesis API.

    Projects represent the top-level organizational unit for tests,
    endpoints, and other resources.

    Examples::

        project = Projects.pull(name="My AI App")
        params = project.parameters()
        print(params.model)
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = True
    icon: Optional[str] = None
    status_id: Optional[str] = None
    user_id: Optional[str] = None
    owner_id: Optional[str] = None
    organization_id: Optional[str] = None
    id: Optional[str] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    parameter_environments: Optional[Dict[str, Any]] = None

    def parameters(
        self,
        *,
        environment: str | None = None,
        experiment_id: str | None = None,
        version: str | None = None,
    ) -> ResolvedParameters:
        """Resolve parameters for this project.

        Delegates to ``Parameters.get(project_id=self.id, ...)``.
        """
        from rhesis.sdk.parameters import Parameters

        return Parameters.get(
            project_id=self.id,
            environment=environment,
            experiment_id=experiment_id,
            version=version,
        )

    def parameter_schema(self) -> ParameterSchema:
        """Fetch the parameter schema for this project."""
        from rhesis.sdk.parameters import Parameters

        return Parameters.schema(project_id=self.id)

    def put_parameter_schema(self, schema: ParameterSchema) -> None:
        """Push a parameter schema to this project."""
        from rhesis.sdk.parameters import Parameters

        Parameters.put_schema(project_id=self.id, schema=schema)


class Projects(BaseCollection):
    """Collection class for Project entities."""

    endpoint = ENDPOINT
    entity_class = Project

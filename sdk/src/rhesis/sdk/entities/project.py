from typing import ClassVar, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.PROJECTS


class Project(BaseEntity):
    """
    Project entity for interacting with the Rhesis API.

    Projects represent the top-level organizational unit for tests, endpoints,
    and other resources. Each project contains its own test sets, endpoints,
    and configurations.

    Examples:
        Create a new project:
        >>> project = Project(name="My AI App", description="Testing my chatbot")
        >>> project.push()

        Load an existing project:
        >>> project = Projects.pull(name="My AI App")
        >>> print(project.name)

        List all projects:
        >>> projects = Projects.all()
        >>> for p in projects:
        ...     print(p.name)
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


class Projects(BaseCollection):
    """Collection class for Project entities."""

    endpoint = ENDPOINT
    entity_class = Project

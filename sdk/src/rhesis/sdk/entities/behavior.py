from typing import ClassVar, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.BEHAVIORS


class Behavior(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: str
    description: str
    id: Optional[str] = None


class Behaviors(BaseCollection):
    endpoint = ENDPOINT

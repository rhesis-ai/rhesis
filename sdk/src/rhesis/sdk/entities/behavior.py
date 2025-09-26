from typing import Optional

from pydantic import BaseModel

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.BEHAVIORS


class BehaviorSchema(BaseModel):
    name: str
    description: str
    id: Optional[str] = None


class Behavior(BaseEntity):
    endpoint = ENDPOINT
    entity_schema = BehaviorSchema

    def __init__(self, name: str, description: str, id: Optional[str] = None) -> None:
        self.name = name
        self.description = description
        self.id = id
        self._set_fields()


class Behaviors(BaseCollection):
    endpoint = ENDPOINT

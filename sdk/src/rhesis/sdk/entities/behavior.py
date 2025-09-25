from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity


class Behavior(BaseEntity):
    endpoint = Endpoints.BEHAVIORS

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)


class Behaviors(BaseCollection):
    endpoint = Endpoints.BEHAVIORS

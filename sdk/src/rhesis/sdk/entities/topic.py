from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TOPICS


class Topic(BaseEntity):
    endpoint = ENDPOINT

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)


class Topics(BaseCollection):
    endpoint = ENDPOINT

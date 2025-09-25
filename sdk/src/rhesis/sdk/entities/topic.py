from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity


class Topic(BaseEntity):
    endpoint = Endpoints.TOPICS

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)


class Topics(BaseCollection):
    endpoint = Endpoints.TOPICS

from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity


class Test(BaseEntity):
    endpoint = Endpoints.TESTS

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)
        self.category = fields.get("category", None)
        self.topic = fields.get("topic", None)
        self.behavior = fields.get("behavior", None)
        self.prompt = fields.get("prompt", None)


class Tests(BaseCollection):
    endpoint = Endpoints.TESTS

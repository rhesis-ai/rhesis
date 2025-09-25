from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.PROMPTS


class Prompt(BaseEntity):
    endpoint = ENDPOINT

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

        self.content = fields.get("content", None)
        self.language_code = fields.get("language_code", None)


class Prompts(BaseCollection):
    endpoint = ENDPOINT

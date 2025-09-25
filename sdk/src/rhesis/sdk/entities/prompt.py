from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity


class Prompt(BaseEntity):
    endpoint = Endpoints.PROMPTS

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

        self.content = fields.get("content", None)
        self.language_code = fields.get("language_code", None)


class Prompts(BaseCollection):
    endpoint = Endpoints.PROMPTS

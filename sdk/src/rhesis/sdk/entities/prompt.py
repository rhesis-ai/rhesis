from typing import Any

from rhesis.sdk.entities import BaseEntity


class Prompt(BaseEntity):
    endpoint = "prompts"

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

        self.content = fields.get("content", None)
        self.language_code = fields.get("language_code", None)

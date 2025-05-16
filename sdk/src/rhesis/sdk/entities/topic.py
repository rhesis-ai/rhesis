from typing import Any

from rhesis.sdk.entities import BaseEntity


class Topic(BaseEntity):
    endpoint = "topics"

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

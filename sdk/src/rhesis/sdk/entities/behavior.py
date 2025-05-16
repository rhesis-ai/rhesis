from typing import Any

from rhesis.sdk.entities import BaseEntity


class Behavior(BaseEntity):
    endpoint = "behaviors"

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

from typing import Any

from rhesis.sdk.entities import BaseEntity


class Category(BaseEntity):
    endpoint = "categories"

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

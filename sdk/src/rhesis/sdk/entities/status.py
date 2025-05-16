from typing import Any

from rhesis.sdk.entities import BaseEntity


class Status(BaseEntity):
    # Yes, this is not pretty, but the plural of status is statuses, check on Merriam-Webster ;)
    endpoint = "statuses"

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)

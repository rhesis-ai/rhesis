from typing import Any

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.STATUSES


class Status(BaseEntity):
    # Yes, this is not pretty, but the plural of status is statuses, check on Merriam-Webster ;)
    endpoint = ENDPOINT

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)


class Statuses(BaseCollection):
    endpoint = ENDPOINT

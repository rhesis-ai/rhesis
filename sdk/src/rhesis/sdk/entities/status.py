from typing import ClassVar, Optional

from rhesis.sdk.clients import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.STATUSES


class Status(BaseEntity):
    # Yes, this is not pretty, but the plural of status is statuses, check on Merriam-Webster ;)
    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: str
    description: Optional[str] = None
    id: Optional[str] = None


class Statuses(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Status

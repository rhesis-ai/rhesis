from typing import ClassVar, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.CATEGORIES


class Category(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: str
    description: str
    id: Optional[str] = None


class Categories(BaseCollection):
    endpoint = ENDPOINT

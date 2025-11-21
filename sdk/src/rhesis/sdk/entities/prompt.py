from typing import ClassVar, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.PROMPTS


class Prompt(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    content: Optional[str] = None
    language_code: Optional[str] = None
    id: Optional[str] = None


class Prompts(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Prompt

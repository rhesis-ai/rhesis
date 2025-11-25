from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TEST_CONFIGURATIONS


class TestConfiguration(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    endpoint_id: str
    category_id: Optional[str] = None
    topic_id: Optional[str] = None
    prompt_id: Optional[str] = None
    use_case_id: Optional[str] = None
    test_set_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    status_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class TestConfigurations(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestConfiguration

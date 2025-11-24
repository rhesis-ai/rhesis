from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TEST_RESULTS


class TestResult(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    test_configuration_id: Optional[str] = None
    test_run_id: Optional[str] = None
    prompt_id: Optional[str] = None
    test_id: Optional[str] = None
    status_id: Optional[str] = None
    test_output: Optional[Dict[str, Any]] = None
    test_metrics: Optional[Dict[str, Any]] = None
    test_reviews: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class TestResults(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestResult

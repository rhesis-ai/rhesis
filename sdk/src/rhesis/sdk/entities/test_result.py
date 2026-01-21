from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.clients import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity
from rhesis.sdk.entities.status import Status

ENDPOINT = Endpoints.TEST_RESULTS


class TestResult(BaseEntity):
    """Test result entity representing execution results from tests.

    Note: This is NOT a pytest test class, despite the 'Test' prefix.
    """

    __test__ = False  # Tell pytest to ignore this class
    endpoint: ClassVar[Endpoints] = ENDPOINT
    test_configuration_id: Optional[str] = None
    test_run_id: Optional[str] = None
    prompt_id: Optional[str] = None
    test_id: Optional[str] = None
    status_id: Optional[str] = None
    status: Optional[Status] = None
    test_output: Optional[Dict[str, Any]] = None
    test_metrics: Optional[Dict[str, Any]] = None
    test_reviews: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class TestResults(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestResult

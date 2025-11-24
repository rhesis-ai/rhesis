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


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(override=True)
    import os

    print(os.getenv("RHESIS_API_KEY"))
    print(os.getenv("RHESIS_API_URL"))

    test_result = TestResult(id="fe64fe45-0a80-49c4-8f0d-286bde4abbff").pull()
    print(test_result)

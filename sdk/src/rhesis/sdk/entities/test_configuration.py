from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Endpoints, Methods, _APIClient
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TEST_CONFIGURATIONS


class TestConfiguration(BaseEntity):
    __test__ = False
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

    def get_test_runs(self):
        """Get all test runs for this test configuration.

        Returns:
            List of test runs for this test configuration
        """
        if self.id is None:
            raise ValueError("Test configuration ID is required")
        client = _APIClient()

        # Filter test runs by test_configuration_id using OData
        params = {"$filter": f"test_configuration_id eq '{self.id}'"}

        response = client.send_request(
            endpoint=Endpoints.TEST_RUNS,
            method=Methods.GET,
            params=params,
        )
        return response


class TestConfigurations(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestConfiguration

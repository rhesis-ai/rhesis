from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TEST_RUNS


class TestRun(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    test_configuration_id: Optional[str] = None
    name: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    status_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    owner_id: Optional[str] = None
    assignee_id: Optional[str] = None
    id: Optional[str] = None

    def get_test_results(self):
        """Get all test results for this test run.

        Returns:
            List of test results for this test run
        """
        if self.id is None:
            raise ValueError("Test run ID is required")
        client = Client()

        # Filter test results by test_run_id using OData
        params = {"$filter": f"test_run_id eq '{self.id}'"}

        response = client.send_request(
            endpoint=Endpoints.TEST_RESULTS,
            method=Methods.GET,
            params=params,
        )
        return response


class TestRuns(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestRun

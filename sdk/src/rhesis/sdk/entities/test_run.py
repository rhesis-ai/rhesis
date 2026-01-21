from enum import Enum
from typing import Any, ClassVar, Dict, Optional

from pydantic import field_validator

from rhesis.sdk.client import Endpoints, Methods, _APIClient
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.TEST_RUNS


class RunStatus(str, Enum):
    """Enum for test run statuses."""

    PROGRESS = "Progress"
    COMPLETED = "Completed"
    PARTIAL = "Partial"
    FAILED = "Failed"


class TestRun(BaseEntity):
    __test__ = False
    endpoint: ClassVar[Endpoints] = ENDPOINT
    test_configuration_id: Optional[str] = None
    name: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    status: Optional[RunStatus] = None
    attributes: Optional[Dict[str, Any]] = None
    owner_id: Optional[str] = None
    assignee_id: Optional[str] = None
    id: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def extract_status(cls, v: Any) -> Optional[str]:
        """Extract name from nested dict if backend returns full Status object."""
        return v.get("name") if isinstance(v, dict) else v

    def get_test_results(self):
        """Get all test results for this test run.

        Returns:
            List of test results for this test run
        """
        if self.id is None:
            raise ValueError("Test run ID is required")
        client = _APIClient()

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

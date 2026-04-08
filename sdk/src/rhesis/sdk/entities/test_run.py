from enum import Enum
from typing import Any, ClassVar, Dict, Optional, Union

from pydantic import field_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity
from rhesis.sdk.entities.stats import TestRunStats, TestRunStatsMode

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
        client = APIClient()

        params = {"$filter": f"test_run_id eq '{self.id}'"}

        response = client.send_request(
            endpoint=Endpoints.TEST_RESULTS,
            method=Methods.GET,
            params=params,
        )
        return response

    def stats(
        self,
        mode: Union[TestRunStatsMode, str] = TestRunStatsMode.ALL,
        **kwargs,
    ) -> TestRunStats:
        """Get statistics scoped to this test run.

        Delegates to ``TestRuns.stats()`` with ``test_run_ids`` set to
        this run's ID.

        Args:
            mode: Data mode controlling which sections are returned.
            **kwargs: Additional filter params (months, top, etc.).

        Returns:
            TestRunStats with the requested sections populated.
        """
        if self.id is None:
            raise ValueError("Test run ID is required")
        return TestRuns.stats(mode=mode, test_run_ids=[self.id], **kwargs)


class TestRuns(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestRun

    @classmethod
    def stats(
        cls,
        mode: Union[TestRunStatsMode, str] = TestRunStatsMode.ALL,
        months: Optional[int] = None,
        top: Optional[int] = None,
        test_run_ids: Optional[list] = None,
        user_ids: Optional[list] = None,
        endpoint_ids: Optional[list] = None,
        test_set_ids: Optional[list] = None,
        status_list: Optional[list] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TestRunStats:
        """Get aggregated test run statistics.

        Args:
            mode: Data mode controlling which sections are returned.
            months: Number of months of historical data (default 6).
            top: Maximum items per ranked list.
            test_run_ids: Filter by specific test run IDs.
            user_ids: Filter by executor user IDs.
            endpoint_ids: Filter by endpoint IDs.
            test_set_ids: Filter by test set IDs.
            status_list: Filter by run status names.
            start_date: Start date (ISO format), overrides months.
            end_date: End date (ISO format), overrides months.

        Returns:
            TestRunStats with the requested sections populated.
        """
        params = {"mode": mode.value if isinstance(mode, Enum) else mode}
        if months is not None:
            params["months"] = months
        if top is not None:
            params["top"] = top
        if test_run_ids is not None:
            params["test_run_ids"] = test_run_ids
        if user_ids is not None:
            params["user_ids"] = user_ids
        if endpoint_ids is not None:
            params["endpoint_ids"] = endpoint_ids
        if test_set_ids is not None:
            params["test_set_ids"] = test_set_ids
        if status_list is not None:
            params["status_list"] = status_list
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date

        client = APIClient()
        response = client.send_request(
            endpoint=Endpoints.TEST_RUNS,
            method=Methods.GET,
            url_params="stats",
            params=params,
        )
        return TestRunStats.model_validate(response)

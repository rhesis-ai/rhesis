from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Union

from rhesis.sdk.clients import APIClient, Endpoints, Methods

if TYPE_CHECKING:
    from rhesis.sdk.entities.file import File
    from rhesis.sdk.entities.stats import TestResultStats, TestResultStatsMode
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

    def get_files(self) -> List["File"]:
        """Get all files attached to this test result.

        Returns:
            List of File instances.
        """
        from rhesis.sdk.entities.file import File

        if not self.id:
            raise ValueError("TestResult must have an ID to get files")
        client = APIClient()
        results = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/files",
        )
        return [File.model_validate(r) for r in results]


class TestResults(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestResult

    @classmethod
    def stats(
        cls,
        mode: Union["TestResultStatsMode", str] = "all",
        months: Optional[int] = None,
        test_run_id: Optional[str] = None,
        test_run_ids: Optional[list] = None,
        test_set_ids: Optional[list] = None,
        behavior_ids: Optional[list] = None,
        category_ids: Optional[list] = None,
        topic_ids: Optional[list] = None,
        status_ids: Optional[list] = None,
        test_ids: Optional[list] = None,
        test_type_ids: Optional[list] = None,
        user_ids: Optional[list] = None,
        assignee_ids: Optional[list] = None,
        owner_ids: Optional[list] = None,
        prompt_ids: Optional[list] = None,
        priority_min: Optional[int] = None,
        priority_max: Optional[int] = None,
        tags: Optional[list] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "TestResultStats":
        """Get aggregated test result statistics.

        Args:
            mode: Data mode controlling which sections are returned.
            months: Number of months of historical data (default 6).
            test_run_id: Filter by a single test run ID.
            test_run_ids: Filter by multiple test run IDs.
            test_set_ids: Filter by test set IDs.
            behavior_ids: Filter by behavior IDs.
            category_ids: Filter by category IDs.
            topic_ids: Filter by topic IDs.
            status_ids: Filter by test status IDs.
            test_ids: Filter by specific test IDs.
            test_type_ids: Filter by test type IDs.
            user_ids: Filter by test creator user IDs.
            assignee_ids: Filter by assignee user IDs.
            owner_ids: Filter by test owner user IDs.
            prompt_ids: Filter by prompt IDs.
            priority_min: Minimum priority (inclusive).
            priority_max: Maximum priority (inclusive).
            tags: Filter by tags.
            start_date: Start date (ISO format), overrides months.
            end_date: End date (ISO format), overrides months.

        Returns:
            TestResultStats with the requested sections populated.
        """
        from enum import Enum

        from rhesis.sdk.entities.stats import TestResultStats

        params: Dict[str, Any] = {"mode": mode.value if isinstance(mode, Enum) else mode}
        _optional = {
            "months": months,
            "test_run_id": test_run_id,
            "test_run_ids": test_run_ids,
            "test_set_ids": test_set_ids,
            "behavior_ids": behavior_ids,
            "category_ids": category_ids,
            "topic_ids": topic_ids,
            "status_ids": status_ids,
            "test_ids": test_ids,
            "test_type_ids": test_type_ids,
            "user_ids": user_ids,
            "assignee_ids": assignee_ids,
            "owner_ids": owner_ids,
            "prompt_ids": prompt_ids,
            "priority_min": priority_min,
            "priority_max": priority_max,
            "tags": tags,
            "start_date": start_date,
            "end_date": end_date,
        }
        for key, val in _optional.items():
            if val is not None:
                params[key] = val

        client = APIClient()
        response = client.send_request(
            endpoint=Endpoints.TEST_RESULTS,
            method=Methods.GET,
            url_params="stats",
            params=params,
        )
        return TestResultStats.model_validate(response)

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from rhesis.sdk.clients import APIClient, Endpoints, Methods

if TYPE_CHECKING:
    from rhesis.sdk.entities.file import File
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

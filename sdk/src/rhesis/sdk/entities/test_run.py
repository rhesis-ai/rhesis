from enum import Enum
from typing import Any, ClassVar, Dict, NoReturn, Optional

from pydantic import field_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods
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

    @property
    def experiment_summary(self) -> Optional[Dict[str, Any]]:
        """Parameter experiment snapshot stored at queue time, if any.

        Returns a dict with keys ``experiment_id``, ``version``,
        ``source``, ``source_environment``, ``experiment_name``, and
        ``parameters`` (the resolved values) when the run was
        executed with parameter management, or ``None`` otherwise.
        """
        if not self.attributes:
            return None
        exp_id = self.attributes.get("parameter_experiment_id")
        if exp_id is None:
            return None
        src = self.attributes.get("parameter_source")
        if src == "label":
            src = "environment"
        src_env = self.attributes.get("parameter_source_environment")
        if src_env is None:
            src_env = self.attributes.get("parameter_source_label")
        return {
            "experiment_id": exp_id,
            "version": self.attributes.get("parameter_version"),
            "source": src,
            "source_environment": src_env,
            "experiment_name": self.attributes.get("parameter_experiment_name"),
            "parameters": self.attributes.get("parameters", {}),
        }

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

    def stats(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError(
            "TestRun.stats() has been removed. Use Insights(entity='test_run', "
            "filters={'test_run_ids': [self.id]}, ...) directly. "
            "See https://docs.rhesis.ai/sdk/statistics."
        )


class TestRuns(BaseCollection):
    endpoint = ENDPOINT
    entity_class = TestRun

    @classmethod
    def stats(cls, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError(
            "TestRuns.stats() has been removed. Use Insights(entity='test_run', ...) "
            "directly. See https://docs.rhesis.ai/sdk/statistics."
        )

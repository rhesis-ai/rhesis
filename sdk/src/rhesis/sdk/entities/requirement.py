from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.REQUIREMENTS


class Requirement(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: Optional[str] = None
    description: Optional[str] = None
    id: Optional[str] = None

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics associated with this requirement.

        Returns:
            Dict containing the list of metrics for this requirement

        Raises:
            ValueError: If requirement ID is not set

        Example:
            >>> requirement = Requirement(id='requirement-123')
            >>> metrics = requirement.get_metrics()
        """
        if self.id is None:
            raise ValueError("Requirement ID is required")

        client = APIClient()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/metrics/",
        )
        return response

    def add_metric(self, metric_id: str) -> Dict[str, Any]:
        """Add a metric to this requirement.

        Args:
            metric_id: The ID of the metric to add to this requirement

        Returns:
            Dict containing the response from adding the metric

        Raises:
            ValueError: If requirement ID is not set

        Example:
            >>> requirement = Requirement(id='requirement-123')
            >>> response = requirement.add_metric('metric-456')
        """
        if self.id is None:
            raise ValueError("Requirement ID is required")

        client = APIClient()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/metrics/{metric_id}",
        )
        return response

    def remove_metric(self, metric_id: str) -> Dict[str, Any]:
        """Remove a metric from this requirement.

        Args:
            metric_id: The ID of the metric to remove from this requirement

        Returns:
            Dict containing the response from removing the metric

        Raises:
            ValueError: If requirement ID is not set

        Example:
            >>> requirement = Requirement(id='requirement-123')
            >>> response = requirement.remove_metric('metric-456')
        """
        if self.id is None:
            raise ValueError("Requirement ID is required")

        client = APIClient()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.DELETE,
            url_params=f"{self.id}/metrics/{metric_id}",
        )
        return response


class Requirements(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Requirement

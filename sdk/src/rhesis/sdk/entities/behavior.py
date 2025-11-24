from typing import Any, ClassVar, Dict, Optional

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.BEHAVIORS


class Behavior(BaseEntity):
    endpoint: ClassVar[Endpoints] = ENDPOINT
    name: Optional[str] = None
    description: Optional[str] = None
    id: Optional[str] = None

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics associated with this behavior.

        Returns:
            Dict containing the list of metrics for this behavior

        Raises:
            ValueError: If behavior ID is not set

        Example:
            >>> behavior = Behavior(id='behavior-123')
            >>> metrics = behavior.get_metrics()
        """
        if self.id is None:
            raise ValueError("Behavior ID is required")

        client = Client()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=f"{self.id}/metrics/",
        )
        return response

    def add_metric(self, metric_id: str) -> Dict[str, Any]:
        """Add a metric to this behavior.

        Args:
            metric_id: The ID of the metric to add to this behavior

        Returns:
            Dict containing the response from adding the metric

        Raises:
            ValueError: If behavior ID is not set

        Example:
            >>> behavior = Behavior(id='behavior-123')
            >>> response = behavior.add_metric('metric-456')
        """
        if self.id is None:
            raise ValueError("Behavior ID is required")

        client = Client()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.POST,
            url_params=f"{self.id}/metrics/{metric_id}",
        )
        return response

    def remove_metric(self, metric_id: str) -> Dict[str, Any]:
        """Remove a metric from this behavior.

        Args:
            metric_id: The ID of the metric to remove from this behavior

        Returns:
            Dict containing the response from removing the metric

        Raises:
            ValueError: If behavior ID is not set

        Example:
            >>> behavior = Behavior(id='behavior-123')
            >>> response = behavior.remove_metric('metric-456')
        """
        if self.id is None:
            raise ValueError("Behavior ID is required")

        client = Client()

        response = client.send_request(
            endpoint=self.endpoint,
            method=Methods.DELETE,
            url_params=f"{self.id}/metrics/{metric_id}",
        )
        return response


class Behaviors(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Behavior


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(override=True)
    behavior = Behaviors.all()

    # pprint(behavior[0].get_metrics())
    behavior = Behavior(id="710a130b-3799-4f83-8258-a3d4709de9fc")
    behavior.remove_metric("efe7ce3a-7026-4b7c-a048-7c7e61b5b977")
